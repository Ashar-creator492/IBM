# Actual Google Colab T4 run

Notebook: https://colab.research.google.com/drive/1ExZBqWgT3UBBkSrq4DDIizvD9zLz1dAa

25-qubit fixed-depot QAOA with row-preserving XY mixer, 8 COBYLA evaluations, 1 layer, 4096 shots, seed 7. Colab UI confirmed T4 allocation; the Aer backend explicitly selected GPU.

Actual solver time: 13.297091673 seconds. Feasible shots: 142. Best route: 0 -> 4 -> 2 -> 5 -> 3 -> 1 -> 0. Cost: 19.87878787878788, equal to the exact classical optimum. COBYLA did not converge within its evaluation budget.

This time excludes installation, runtime allocation, and browser interaction. This is classical GPU simulation, not quantum hardware or evidence of quantum speedup. The unmodified downloaded result is stored in six_gpu_result.json.
