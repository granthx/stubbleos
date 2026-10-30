# StubbleOS Evaluation Matrix & Benchmark Results

> **Note**: All results are generated from reproducible, seeded discrete-event simulation runs.

### Scenario: `baseline-district`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.6% | 1.45 | Reference (0.0%) | -0.85% | 704.9 | 1.3% | 0.0 |
| `baseline_b` | 89.9% | 29.52 | -1935.9% | 1.28% | 0.0 | 1.7% | 18.4 |
| `stubbleos_centralized` | 99.3% | 2.01 | -38.4% | -0.47% | 64.5 | 1.8% | 1044.4 |
| `stubbleos_decentralized` | 89.9% | 28.94 | -1896.1% | 1.28% | 0.0 | 1.7% | 184.3 |


### Scenario: `low-trust`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.6% | 1.45 | Reference (0.0%) | -0.47% | 708.1 | 1.3% | 0.0 |
| `baseline_b` | 89.9% | 29.23 | -1915.7% | 1.28% | 0.0 | 1.7% | 18.4 |
| `stubbleos_centralized` | 99.1% | 2.30 | -58.4% | -0.20% | 60.7 | 1.8% | 1061.9 |
| `stubbleos_decentralized` | 89.9% | 29.51 | -1935.2% | 1.28% | 0.0 | 1.7% | 184.3 |


### Scenario: `machine-scarce`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.5% | 1.72 | Reference (0.0%) | 0.06% | 736.1 | 3.9% | 0.0 |
| `baseline_b` | 90.1% | 28.66 | -1566.5% | 1.29% | 50.0 | 4.8% | 18.8 |
| `stubbleos_centralized` | 97.1% | 7.50 | -335.9% | 1.32% | 90.4 | 5.1% | 695.0 |
| `stubbleos_decentralized` | 90.1% | 28.66 | -1566.5% | 1.29% | 44.3 | 4.9% | 184.3 |


### Scenario: `rain-shock`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.8% | 0.59 | Reference (0.0%) | -0.49% | 699.4 | 1.3% | 0.0 |
| `baseline_b` | 89.9% | 29.51 | -4901.7% | 1.28% | 35.4 | 1.6% | 18.4 |
| `stubbleos_centralized` | 98.2% | 4.62 | -683.1% | -0.74% | 142.1 | 1.7% | 1515.2 |
| `stubbleos_decentralized` | 89.9% | 29.51 | -4901.7% | 1.28% | 35.4 | 1.6% | 184.3 |

