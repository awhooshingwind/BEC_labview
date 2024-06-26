import numpy as np
import math

"""
To function within LabView Python node, whole routine needs to be wrapped
in a callable function - takes a path to the protocol.txt file as an argument,
returns a cluster that gets passed into global vars for handing off to FPGAs
"""

def get_actions(filename):
    actionlist = []  # time, channel, actionidentifier, action parameter
    # Note: Action parameters are used for dac values to avoid writing out
    # too many individual TTL flips when a dacvalue or dacaddress get changed

    # When encountering a GPIB command, we will store it separately
    # and then sort just the GPIB command at the end.
    # Our GPIBloop VI requires a timeorderd list of times, addess string, commandstring
    GPIBmatrix = []

    #Some channel definitions of hardwired channels
    dacdatabits = [0,15] #16 data bits 
    dactrigger = 16 
    dacaddressbits = [1, 4] # 4 address bits (on block 1, DIO 20:17)
    # TTLs = [32, 95] # 4 16 bit blocks
    # bonus = [21, 30]
    # board_sync = 63 # reserved line for board sync trigger

    # Helper routines
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

    def setdacbits(time, dacaddress, databits):
        # defined function for this cause this sequence is often used in all ramps

        # put address bits on bus for dacs. This is action identifier 2.
        actionlist.append([time, 0, 2, dacaddress])
        # put the data on the databus for the dacs. This is action identifier 3.
        actionlist.append([time, 0, 3, databits])
        # Run the DAC trigger. Need two transitions to load then latch DAC data
        # start high, prevents address bits from loading data into buffers too soon
        actionlist.append([time, dactrigger, 1, 0]) 
        actionlist.append([time + 1, dactrigger, 0, 0]) # low + address loads into buffers
        actionlist.append([time + 2, dactrigger, 1, 0]) # need one more strobe to latch into ad7846
        actionlist.append([time + 3, dactrigger, 0, 0])
        actionlist.append([time + 4, dactrigger, 1, 0]) # default trigger to high


    with open(filename) as f:
        # This reads in a batch file with tab separated columns.
        # It also automatically takes off the \n in the lines.
        # Using tab separated columnns instead of blanks is important e.g. for GPIB strings
        # GPIB strings can contain spaces but the whole string should be one parameter.
        commandlines = f.read().splitlines()

        for lines in commandlines:
            commands = lines.split("\t")

            if commands[0] == "on":
                time = int(commands[1])
                channel = int(commands[2])
                actionlist.append([time, channel, 1, 0])  # action 1 means set a TTL high.
                # parameter is not used for this, so set it to 0.

            elif commands[0] == "off":
                time = int(commands[1])
                channel = int(commands[2])
                actionlist.append([time, channel, 0, 0])  # action 0 means set a TTL low
                # parameter is not used for this, so set it to 0.

            elif commands[0] == "raise":
                time = int(commands[1])
                channel = int(commands[2])
                duration = int(commands[3])
                actionlist.append([time, channel, 1, 0])
                actionlist.append([time + duration, channel, 0, 0])
                # parameter is not used for this, so set it to 0.

            elif commands[0] == 'dacvolts':  
                # dacvolts, xt, dacchannel, value
                time = int(commands[1])
                dacaddress = int(commands[2])
                databits =  volts_to_dacbits(float(commands[3]))
                #put this into a separate function cause used in all ramps etc.
                setdacbits(time,dacaddress,databits)

            elif commands[0] == "linrampbits": 
                # starttime, channel, startbit, endbit, duration, Nsteps
                starttime = int(commands[1])
                dacaddress = int(commands[2])
                startbit = int(commands[3])
                endbit = int(commands[4])
                duration = int(commands[5])
                Npoints = int(commands[6])
                # In loop, don't do last step cause want to do this one without rounding
                ramptimes = np.linspace(starttime, starttime+duration, Npoints-1, endpoint=False)
                rampbits = np.linspace(startbit, endbit, Npoints-1, endpoint=False)
                for tr, br in zip(ramptimes, rampbits):
                    # Don't use np.round for time: Need to avoid two things happening at same time.
                    setdacbits(int(np.floor(tr)), dacaddress, int(np.round(br)))
                    # for the last step we don't want to round but be precise:
                    setdacbits(starttime + duration, dacaddress, endbit)
            
            elif commands[0] == "linrampvolts": 
                # starttime, channel, start volt, endvolt, duration, Nsteps
                starttime = int(commands[1])
                dacaddress = int(commands[2])
                startbit = volts_to_dacbits(float(commands[3]))
                endbit = volts_to_dacbits(float(commands[4]))
                duration = int(commands[5])
                Npoints = int(commands[6])
                # In loop, don't do last step cause want to do this one without rounding
                ramptimes = np.linspace(starttime, starttime+duration, Npoints-1, endpoint=False)
                rampbits = np.linspace(startbit, endbit, Npoints-1, endpoint=False)
                for tr, br in zip(ramptimes, rampbits):
                    setdacbits(int(np.floor(tr)), dacaddress, int(np.round(br)))
                    # for the last step we don't want to round but be precise:
                    setdacbits(starttime + duration, dacaddress, endbit)

            elif commands[0] == "GPIBwrite":
                time = int(commands[1])
                address = int(commands[2])
                Gcomms = commands[3]  # this is string! Not numbers.
                GPIBmatrix.append([str(time), str(address), Gcomms])

    # Now that we have all actions spelled out (i.e. all individual bit settings),
    # need to sort this matrix by time
    actions_np = np.array(actionlist)

    # Now sort the actions by the first column, which is their times
    actions_np = actions_np[actions_np[:, 0].argsort()]
    uniquetimes = len(np.unique(actions_np[:,0]))
    num_DIO_blocks = 6
    main_portlist = np.zeros((uniquetimes, num_DIO_blocks), dtype = np.uint16)
    aux_portlist = np.zeros((uniquetimes, num_DIO_blocks), dtype = np.uint16)
    xtlist = -1*np.ones(uniquetimes, dtype=np.int32)
    i=-1
    previoustime = -1

    for time, channel, action, param in actions_np:
        block_index = 0
        portlist = main_portlist
        other = aux_portlist
        # Shift channel into appropriate DIO block and for bitwise operations
        if channel >= 100:
            channel -= 100
            portlist = aux_portlist
            other = main_portlist
        
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
    main_portlist as all the states of the TTLs (channels 1-96)**
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

filename = "FPGA\\files\GetMOTGoing.txt"
# filename = 'files\ecgroutine.txt'
# filename = 'test_batch.txt'
# filename = 'sequential_batch.txt'
# filename = 'dac_test.txt'


print(get_actions(filename)) # for testing

