import numpy as np
import math

"""
To function within LabView Python node, whole routine needs to be wrapped
in a callable function - takes a path to the protocol.txt file as an argument,
returns a cluster that gets passed into global vars for handing off to FPGAs
"""

# Some channel definitions of hardwired channels
dacdatabits = [0,15] # 16 data bits 
dactrigger = 16 
dacaddressbits = [1, 4] # 4 address bits (on block 1, DIO 20:17)
# TTLs = [32, 95] # 4 16-bit blocks
# bonus = [21, 30]
# board_sync = 63 # reserved line for board sync trigger

# Helper functions
def replacebits(number, newbits, i, j):
    # Replaces bits i through j of number by newbits
    mask = (1 << (j - i + 1)) - 1  # creates j-i+1 ones
    cleared = number & ~(mask << i)  # shift mask into place and invert
    newbits = newbits << i  # shift the new bits into place
    number = cleared | newbits
    return number

def volts_to_dacbits(volts):
# using 16bit int to cover range -10V to 10V (0:65535)
    return math.ceil((volts+10)/20 * 65535)

def setdacbits(time, dacaddress, databits, actions):
    # defined function for this cause this sequence is often used in all ramps
    # put address bits on bus for dacs. This is action identifier 2.
    actions.append([time, 0, 2, dacaddress])
    # put the data on the databus for the dacs. This is action identifier 3.
    actions.append([time, 0, 3, databits])
    # Run the DAC trigger. Need two transitions to load then latch DAC data
    # start high, prevents address bits from loading data into buffers too soon
    actions.append([time, dactrigger, 1, 0]) 
    actions.append([time + 1, dactrigger, 0, 0]) # low + address loads into buffers
    actions.append([time + 2, dactrigger, 1, 0]) # need one more strobe to latch into ad7846
    actions.append([time + 3, dactrigger, 0, 0])
    actions.append([time + 4, dactrigger, 1, 0]) # default trigger to high

# Command handling functions
def set_TTL(command, actions):
    # reusable for processing TTL related commands
    time = int(command[1])
    channel = int(command[2])
    action = 1 if command[0] == 'on' or command[0] == 'raise' else 0
    actions.append([time, channel, action, 0])
    if command[0] == 'raise':
        duration = int(command[3])
        actions.append([time + duration, channel, 0, 0])

def set_dac(command, actions):
    time = int(command[1])
    dac_channel = int(command[2])
    dac_data = volts_to_dacbits(float(command[3])) if 'volts' in command[0] else int(command[3])
    setdacbits(time, dac_channel, dac_data, actions)

def sigbits(bmin, bmax, num_steps):
    # helper for sigmoid ramping
    L = bmax-bmin
    xvals = np.linspace(-6, 6, num_steps)
    return (L / (1 + np.exp(-xvals))) + bmin

def process_ramp(command, actions):
    start = int(command[1])
    dac_channel = int(command[2])
    start_value = volts_to_dacbits(float(command[3])) if 'volts' in command[0] else int(command[3])
    end_value = volts_to_dacbits(float(command[4])) if 'volts' in command[0] else int(command[4])
    duration = int(command[5])
    Npoints = int(command[6])
    end = start+duration
    if 'lin' in command[0]:
        # Use np.linspace for linear ramping - can add other types of ramp logic here later
        ramptimes = np.linspace(start, end, Npoints-1, endpoint=False)
        rampbits = np.linspace(start_value, end_value, Npoints-1, endpoint=False)
    if 'sig' in command[0]:
        ramptimes = np.linspace(start, end, Npoints-1, endpoint=False)
        rampbits = sigbits(start_value, end_value, Npoints-1)
    for tr, br in zip(ramptimes, rampbits):
        setdacbits(int(np.floor(tr)), dac_channel, int(np.round(br)), actions)
        setdacbits(start + duration, dac_channel, end_value, actions)
    
        
def process_GPIB(command, GPIBmatrix):
    time = str(command[1])
    address = str(command[2])
    Gcomms = command[3]  # this is string! Not numbers.
    GPIBmatrix.append([time, address, Gcomms])

# Dict of command types
command_dispatch = {
    'on': set_TTL,
    'off': set_TTL,
    'raise': set_TTL,
    'dacvolts': set_dac,
    'linrampbits': process_ramp,
    'linrampvolts': process_ramp,
    'sigrampbits': process_ramp,
    'sigrampvolts': process_ramp,
    'GPIBwrite': process_GPIB
}

def register_command(command_row, sorting_list):
    comm_type = command_row[0]
    if comm_type in command_dispatch:
        func = command_dispatch[comm_type]
        func(command_row, sorting_list)

# Main routine
def get_actions(filename):
    actionlist = []  # time, channel, actionidentifier, action parameter
    # Note: Action parameters are used for dac values to avoid writing out
    # too many individual TTL flips when a dacvalue or dacaddress get changed

    # When encountering a GPIB command, we will store it separately
    # and then sort just the GPIB command at the end.
    # Our GPIBloop VI requires a timeorderd list of times, address string, commandstring
    GPIBmatrix = []

    with open(filename) as f:
        # This reads in a batch file with tab separated columns.
        # It also automatically takes off the \n in the lines.
        # Using tab separated columnns instead of blanks is important e.g. for GPIB strings
        # GPIB strings can contain spaces but the whole string should be one parameter.
        commandlines = f.read().splitlines()

        for lines in commandlines:
            command_row = lines.split("\t")
            if 'GPIB' in command_row[0]:
                register_command(command_row, GPIBmatrix)
            else:
                register_command(command_row, actionlist)

    # Now that we have all actions spelled out (i.e. all individual bit settings),
    # need to sort this matrix by time
    actions_np = np.array(actionlist)
    print(actions_np)

    # Now sort the actions by the first column, which is their times
    actions_np = actions_np[actions_np[:, 0].argsort()]
    uniquetimes = len(np.unique(actions_np[:,0]))
    num_DIO_blocks = 6 # for the RMC on sbRIO 9606
    main_portlist = np.zeros((uniquetimes, num_DIO_blocks), dtype = np.uint16)
    aux_portlist = np.zeros((uniquetimes, num_DIO_blocks), dtype = np.uint16)
    xtlist = -1*np.ones(uniquetimes, dtype=np.int32)
    i=-1
    previoustime = -1

    # From time-ordered actions array, generate portlists (FPGA output)
    for time, channel, action, param in actions_np:
        block_index = 0
        portlist = main_portlist
        other = aux_portlist
        # Switch 'working' list if aux channel (ie 101 -> 01 on aux board)
        if channel >= 100:
            channel -= 100
            portlist = aux_portlist
            other = main_portlist
        # Select block index before doing bitwise operations
        block_index = channel // 16
        channel -= (block_index*16)
        channel = int(channel)
        #Do we have a new time?
        time = int(time)
        
        #Check if this is a new time. If so, add it to xt,
        #and copy previous port state to the new time before modifying it.
        if time > previoustime: #We have a new time
            i +=1
            previoustime = time
            xtlist[i] = time
            portlist[i] = portlist[i-1]
            other[i] = other[i-1]

        temp = int(portlist[i][block_index])
        if action == 0:  # set a TTL to low
            portlist[i][block_index] = temp & ~(1 << channel)
        elif action == 1:  # set a TTL to high
            portlist[i][block_index] = temp | (1 << channel)
        elif action == 2:  # replace dac address bits by param
            temp = int(portlist[i][1]) # DAC address bits in block 1
            portlist[i][1] = replacebits(temp, param, dacaddressbits[0], dacaddressbits[1])
        elif action == 3:  # replace dac data bits by param
            temp = int(portlist[i][0]) # DAC data bits on block 0
            portlist[i][0] = replacebits(temp, param, dacdatabits[0], dacdatabits[1])

    # Now we need to timeorder the GPIBmatrix
    GPIBmatrix = sorted(GPIBmatrix, key=lambda x: int(x[0]))

    """
    Now we can hand over the results to Labview.
    We have for all the TTLs:
    xtlist for all the times of TTLs
    main_portlist as all the states of the TTLs (channels 1-96)
    aux_portlist for channels > 100 (shifted down by 100, so 1-96 on aux board)
    and for all the GPIB commands:    
    GPIBmatrix    
    """
    xtlist = xtlist.astype(np.uint32)

    cluster = (xtlist, GPIBmatrix, main_portlist, aux_portlist)
    
    ## For testing/verify portlists
    # with open('main_portlist.txt', 'w') as f:
    #    for line in main_portlist:
    #        f.write(f"{line}\n")
    # with open('aux_portlist.txt', 'w') as f:
    #     for line in aux_portlist:
    #         f.write(f"{line}\n") 

    return cluster

# For testing

# filename = "FPGA\\files\\GetMOTGoing.txt"
# filename = 'test_batch.txt'
# filename = 'sequential_batch.txt'
# filename = 'dac_test.txt'

# print(get_actions(filename)) # for testing

