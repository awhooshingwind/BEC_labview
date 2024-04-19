# Batch File Generator for testing
import random
import numpy as np

num_commands = 100
xt_end = 5e2

# Define all possible channels
all_channels = list(range(40)) + list(range(100,140))
# all_channels = [1, 101]

# Define forbidden channels
forbidden_channels = [48, 63, 132, 147] + list(range(96, 100)) + list(range(196, 200))

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
def random_test():
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

def generate_sequential_activation(file_name, start_time, time_step, channels):
    with open(file_name, 'w') as f:
        current_time = start_time
        for channel in channels:
            line_on = write_line('on', current_time, channel)
            f.write(line_on + '\n')
            current_time += time_step


def transience_tests(file_name, test_line, rate=int(5e4), num_channels=8):
    channels = list(range(num_channels))
    def toggle_line(line, state, time):
        if 0 <= line < num_channels:
            cmd = write_line(state, time, line)
            f.write(cmd + '\n')

    with open(file_name, 'w') as f:
        curr_time = 0
        # # start with test_line on
        # toggle_line(test_line, 'on', curr_time)
        # # toggle adjacent lines on
        # for i in range(1, int(num_channels/2)):
        #     curr_time += rate
        #     toggle_line(test_line+i, 'on', curr_time)
        #     toggle_line(test_line-i, 'on', curr_time)
        # # toggle test line off
        # curr_time += rate
        toggle_line(test_line, 'off', curr_time)
        curr_time += 2*rate
        # flip everything else on
        for i in range(num_channels):
            # curr_time += rate
            if i != test_line:
                toggle_line(i, 'on', curr_time)
                # flip all off after some delay
                toggle_line(i, 'off', curr_time+2*rate)
        # curr_time += 2*rate
        
       
        
            
        
# Usage

# generate_sequential_activation('sequential_batch.txt', 0, 500000, channels) # or any other range or list of channels
# random_test()
transience_tests('toggle_test.txt', 5)
