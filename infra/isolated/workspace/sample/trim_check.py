import time

for index in range(520):
    print(f"trim-line-{index:04d}", flush=True)
    if index % 4 == 3:
        time.sleep(0.3)
