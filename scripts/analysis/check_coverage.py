import subprocess
import sys

# Run pytest with coverage
result = subprocess.run(
    [sys.executable, '-m', 'pytest', 
     'execution_layer/lighter/tests/test_signal_executor.py',
     '--cov=execution_layer.lighter.signal_executor',
     '--cov-report=term', '-q', '--tb=no'],
    capture_output=True, text=True, cwd=r'c:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer'
)

# Print last 30 lines (coverage summary)
lines = result.stdout.split('\n')
for line in lines[-30:]:
    if line.strip():
        print(line)

if result.returncode != 0:
    print(f"\nExit code: {result.returncode}")
