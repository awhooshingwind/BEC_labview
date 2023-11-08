# Batch File Generator for testing
import random
import numpy as np

num_commands = 100
xt_end = 5e6

# Define all possible channels
# all_channels = list(range(96*2))
all_channels = [1, 101]

# Define forbidden channels
forbidden_channels = [48, 63, 132, 147] + list(range(95, 100)) + list(range(195, 200))

# Create an array of allowed channels by excluding forbidden channels
channels = np.array([ch for ch in all_channels if ch not in forbidden_channels])

# commands = ['on', 'off', 'raise', 'dacvolts' , 'linrampbits', 'GPIBwrite']
# weights = [5, 5, 3, 3, 1, 1]

commands = ['on', 'off', 'GPIBwrite']
weights = [6, 2, 1]

def write_line(*args):
    line = ''
    for arg in args:
        line += (f"{arg}\t")
    # print(line)
    return line.strip()

with open('test_batch.txt', 'w') as f:
    for i in range(num_commands):
        command = np.random.choice(commands, p=np.array(weights)/sum(weights))
        channel = random.choice(channels)
        time = random.randint(0, xt_end)
        if command == 'dacvolts': #xt, dacdata, dacchannel, value
            param1 = random.randint(16, 20) # dacchannel
            param2 = random.uniform(-10, 10) # value
            line = write_line(command, time, param1, param2)

        elif command == 'raise':
            param1 = random.randint(40,1000)
            line = write_line(command, time, channel, param1)
        elif command == 'linrampbits': #starttime, channel, startbit, endbit, duration, Nsteps
            param1 = random.randint(0,2000)
            param2 = param1 + random.randint(50, 900)
            param3 = random.randint(100,300)
            param4 = random.randint(4,600)
            line = write_line(command, time, channel, param1, param2, param3, param4)
        elif command == 'GPIBwrite':
            param1 = random.randint(1,12)
            str = f'FREQ {random.randint(1e3,3e3)};AMPL {random.randint(-9, 2)}DBM;OFSL 0;MODL 1;TYPE 3;SFNC 5;SDEV 30E6;ENBL 1'
            line = write_line(command, time, param1, str)
        else:
            line = write_line(command, time, channel)
        f.write(line + '\n')