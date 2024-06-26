'''
Hamiltonian Simulation Benchmark Program - Qiskit
(C) Quantum Economic Development Consortium (QED-C) 2024.
'''

'''
This program benchmarks Hamiltonian simulation using Qiskit. 
The central function is the `run()` method, which orchestrates the entire benchmarking process.

HamiltonianSimulation forms the trotterized circuit used in the benchmark.

HamiltonianSimulationExact runs a classical calculation that perfectly simulates hamiltonian evolution, although it does not scale well. 
'''

import json
import os
import sys
import time
from ham_class import HamiltonianKernel, HeisenbergHamiltonianKernel, TfimHamiltonianKernel
import numpy as np

sys.path[1:1] = ["_common", "_common/qiskit"]
sys.path[1:1] = ["../../_common", "../../_common/qiskit"]
import execute as ex
import metrics as metrics

from hamiltonian_simulation_kernel import HamiltonianSimulation, kernel_draw


# Benchmark Name
benchmark_name = "Hamiltonian Simulation"

np.random.seed(0)

verbose = False


# Import precalculated data to compare against
filename = os.path.join(os.path.dirname(__file__), os.path.pardir, "_common", "precalculated_data.json")
with open(filename, 'r') as file:
    data = file.read()
precalculated_data = json.loads(data)

# Creates a key for distribution of initial state for method = 3.
def key_from_initial_state(num_qubits, num_shots, init_state, random_pauli_flag):
    def generate_pattern(starting_bit):
        pattern = ''.join([str((i + starting_bit) % 2) for i in range(num_qubits)])
        return pattern

    correct_dist = {}

    if init_state == "checkerboard":
        if random_pauli_flag:
            starting_bit = 0 if num_qubits % 2 != 0 else 1
        else:
            starting_bit = 1 if num_qubits % 2 != 0 else 0
        correct_dist[generate_pattern(starting_bit)] = num_shots
    elif init_state == "ghz":
        correct_dist = {
            '0' * num_qubits: num_shots/2,
            '1' * num_qubits: num_shots/2
        }

    return correct_dist


############### Result Data Analysis

#def analyze_and_print_result(qc: QuantumCircuit, result, num_qubits: int,
def analyze_and_print_result(qc, result, num_qubits: int,
            type: str, num_shots: int, hamiltonian: str, method: int, random_pauli_flag: bool, init_state: str) -> tuple:
    """
    Analyze and print the measured results. Compute the quality of the result based on operator expectation for each state.

    Args:
        qc (QuantumCircuit): The quantum circuit.
        result: The result from the execution.
        num_qubits (int): Number of qubits.
        type (str): Type of the simulation.
        num_shots (int): Number of shots.
        hamiltonian (str): Which hamiltonian to run. "heisenberg" by default but can also choose "TFIM". 
        method (int): Method for fidelity checking (1 for noiseless trotterized quantum, 2 for exact classical), 3 for mirror circuit.

    Returns:
        tuple: Counts and fidelity.
    """
    counts = result.get_counts(qc)
    if verbose:
        print(f"For type {type} measured: {counts}")

    hamiltonian = hamiltonian.strip().lower()

    # Precalculated correct distribution
    if method == 1 and hamiltonian == "heisenberg":
        correct_dist = precalculated_data[f"Heisenberg - Qubits{num_qubits}"]
    elif method == 2 and hamiltonian == "heisenberg":
        correct_dist = precalculated_data[f"Exact Heisenberg - Qubits{num_qubits}"]
    elif method == 1 and hamiltonian == "tfim":
        correct_dist = precalculated_data[f"TFIM - Qubits{num_qubits}"]
    elif method == 2 and hamiltonian == "tfim":
        correct_dist = precalculated_data[f"Exact TFIM - Qubits{num_qubits}"]
    elif method == 3:
        correct_dist = key_from_initial_state(num_qubits, num_shots, init_state, random_pauli_flag )
    else:
        raise ValueError("Method is not 1 or 2 or 3, or hamiltonian is not tfim or heisenberg.")

    if verbose:
        print(f"Correct dist: {correct_dist}")

    # Use polarization fidelity rescaling
    fidelity = metrics.polarization_fidelity(counts, correct_dist)
    return counts, fidelity


############### Benchmark Loop

def run(min_qubits: int = 2, max_qubits: int = 8, max_circuits: int = 3,
        skip_qubits: int = 1, num_shots: int = 100,
        hamiltonian: str = "heisenberg", method: int = 1,
        use_XX_YY_ZZ_gates: bool = False, random_pauli_flag: bool = True, init_state: str = "checkerboard",
        backend_id: str = None, provider_backend = None,
        hub: str = "ibm-q", group: str = "open", project: str = "main", exec_options = None,
        context = None, api = None):
    """
    Execute program with default parameters.

    Args:
        min_qubits (int): Minimum number of qubits (smallest circuit is 2 qubits).
        max_qubits (int): Maximum number of qubits.
        max_circuits (int): Maximum number of circuits to execute per group.
        skip_qubits (int): Increment of number of qubits.
        num_shots (int): Number of shots for each circuit execution.
        use_XX_YY_ZZ_gates (bool): Flag to use unoptimized XX, YY, ZZ gates.
        backend_id (str): Backend identifier for execution.
        provider_backend: Provider backend instance.
        hub (str): IBM Quantum hub.
        group (str): IBM Quantum group.
        project (str): IBM Quantum project.
        exec_options: Execution options.

        hamiltonian (str): Which hamiltonian to run. "heisenberg" by default but can also choose "TFIM". 
        method (int): Method for fidelity checking (1 for noiseless trotterized quantum, 2 for exact classical), 3 for mirror circuit.
        context: Execution context.

    Returns:
        None
    """
    print(f"{benchmark_name} Benchmark Program - Qiskit")
    
    # Validate parameters (smallest circuit is 2 qubits)
    max_qubits = max(2, max_qubits)
    min_qubits = min(max(2, min_qubits), max_qubits)
    if min_qubits % 2 == 1: min_qubits += 1  # min_qubits must be even
    skip_qubits = max(1, skip_qubits)

    # Create context identifier
    if context is None: context = f"{benchmark_name} Benchmark"
    
    # Set the flag to use an XX YY ZZ shim if given
    if use_XX_YY_ZZ_gates:
        print("... using unoptimized XX YY ZZ gates")
    
    # Initialize metrics module
    metrics.init_metrics()

    # Define custom result handler
    def execution_handler(qc, result, num_qubits, type, num_shots):
        # Determine fidelity of result set
        num_qubits = int(num_qubits)
        counts, expectation_a = analyze_and_print_result(qc, result, num_qubits, type, num_shots, hamiltonian, method, random_pauli_flag, init_state)
        metrics.store_metric(num_qubits, type, 'fidelity', expectation_a)

    # Initialize execution module using the execution result handler above and specified backend_id
    ex.init_execution(execution_handler)
    ex.set_execution_target(backend_id, provider_backend=provider_backend,
            hub=hub, group=group, project=project, exec_options=exec_options,
            context=context)

    # Execute Benchmark Program N times for multiple circuit sizes
    # Accumulate metrics asynchronously as circuits complete
    for num_qubits in range(min_qubits, max_qubits + 1, skip_qubits):

        # Reset random seed
        np.random.seed(0)

        # Determine number of circuits to execute for this group
        num_circuits = max(1, max_circuits)
        
        print(f"************\nExecuting [{num_circuits}] circuits with num_qubits = {num_qubits}")

        # Parameters of simulation
        #### CANNOT BE MODIFIED W/O ALSO MODIFYING PRECALCULATED DATA #########
        w = precalculated_data['w']  # Strength of disorder
        k = precalculated_data['k']   # Trotter error.
               # A large Trotter order approximates the Hamiltonian evolution better.
               # But a large Trotter order also means the circuit is deeper.
               # For ideal or noise-less quantum circuits, k >> 1 gives perfect Hamiltonian simulation.
        t = precalculated_data['t']  # Time of simulation
        #######################################################################

        # Loop over only 1 circuit
        for circuit_id in range(num_circuits):
            ts = time.time()
            hx = precalculated_data['hx'][:num_qubits]  # Precalculated random numbers between [-1, 1]
            hz = precalculated_data['hz'][:num_qubits]

            if hamiltonian == "heisenberg" :
                qc_object = HeisenbergHamiltonianKernel(num_qubits, K=k, t=t,
                        hamiltonian=hamiltonian,
                        w=w, hx = hx, hz = hz, 
                        use_XX_YY_ZZ_gates = use_XX_YY_ZZ_gates,
                        method = method, random_pauli_flag = random_pauli_flag)
            
            if hamiltonian == "tfim" :
                qc_object = TfimHamiltonianKernel(num_qubits, K=k, t=t,
                        hamiltonian=hamiltonian,
                        w=w, hx = hx, hz = hz, 
                        use_XX_YY_ZZ_gates = use_XX_YY_ZZ_gates,
                        method = method, random_pauli_flag = random_pauli_flag)
            
            qc = qc_object.overall_circuit()
                    
            metrics.store_metric(num_qubits, circuit_id, 'create_time', time.time() - ts)
            qc.draw()

            # Submit circuit for execution on target (simulator, cloud simulator, or hardware)
            ex.submit_circuit(qc, num_qubits, circuit_id, num_shots)
        
        # Wait for some active circuits to complete; report metrics when groups complete
        ex.throttle_execution(metrics.finalize_group)
    
    # Wait for all active circuits to complete; report metrics when groups complete
    ex.finalize_execution(metrics.finalize_group)

    ##########
    
    # draw a sample circuit
    kernel_draw(hamiltonian, use_XX_YY_ZZ_gates, method, random_pauli_flag)
       
    # Plot metrics for all circuit sizes
    options = {"ham": hamiltonian, "method":method, "shots": num_shots, "reps": max_circuits}
    if use_XX_YY_ZZ_gates: options.update({ "xyz": use_XX_YY_ZZ_gates })
    metrics.plot_metrics(f"Benchmark Results - {benchmark_name} - Qiskit", options=options)


#######################
# MAIN

import argparse
def get_args():
    parser = argparse.ArgumentParser(description="Bernstei-Vazirani Benchmark")
    #parser.add_argument("--api", "-a", default=None, help="Programming API", type=str)
    #parser.add_argument("--target", "-t", default=None, help="Target Backend", type=str)
    parser.add_argument("--backend_id", "-b", default=None, help="Backend Identifier", type=str)
    parser.add_argument("--num_shots", "-s", default=100, help="Number of shots", type=int)
    parser.add_argument("--num_qubits", "-n", default=0, help="Number of qubits (min = max = N)", type=int)
    parser.add_argument("--min_qubits", "-min", default=3, help="Minimum number of qubits", type=int)
    parser.add_argument("--max_qubits", "-max", default=8, help="Maximum number of qubits", type=int)
    parser.add_argument("--skip_qubits", "-k", default=1, help="Number of qubits to skip", type=int)
    parser.add_argument("--max_circuits", "-c", default=3, help="Maximum circuit repetitions", type=int)     
    parser.add_argument("--hamiltonian", "-ham", default="heisenberg", help="Name of Hamiltonian", type=str)
    parser.add_argument("--method", "-m", default=1, help="Algorithm Method", type=int)
    parser.add_argument("--use_XX_YY_ZZ_gates", action="store_true", help="Use explicit XX, YY, ZZ gates")
    #parser.add_argument("--theta", default=0.0, help="Input Theta Value", type=float)
    parser.add_argument("--nonoise", "-non", action="store_true", help="Use Noiseless Simulator")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose")
    parser.add_argument("--random_pauli_flag", "-ranp", action="store_true", help="random pauli flag")
    parser.add_argument("--init_state", "-init", default="checkerboard", help="initial state")
    return parser.parse_args()
 
# if main, execute method
if __name__ == '__main__':   
    args = get_args()
    
    # configure the QED-C Benchmark package for use with the given API
    # (done here so we can set verbose for now)
    #PhaseEstimation, kernel_draw = qedc_benchmarks_init(args.api)
    
    # special argument handling
    ex.verbose = args.verbose
    verbose = args.verbose
    
    if args.num_qubits > 0: args.min_qubits = args.max_qubits = args.num_qubits
    
    # execute benchmark program
    run(min_qubits=args.min_qubits, max_qubits=args.max_qubits,
        skip_qubits=args.skip_qubits, max_circuits=args.max_circuits,
        num_shots=args.num_shots,
        hamiltonian=args.hamiltonian,
        method=args.method,
        random_pauli_flag=args.random_pauli_flag,
        use_XX_YY_ZZ_gates =args.use_XX_YY_ZZ_gates,
        init_state = args.init_state,
        #theta=args.theta,
        backend_id=args.backend_id,
        exec_options = {"noise_model" : None} if args.nonoise else {},
        #api=args.api
        )
