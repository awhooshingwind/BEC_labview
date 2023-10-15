# -*- coding: utf-8 -*-
"""
P. Engels 3/2023

We first run through all commands and write them out in individual bit flips,
called actions. An actionlist line consists of time, channel, actionidentifier, parameter.
Then we time order all actions.
Finally we assemble all the actions that occur at a given time into a port value.

This avoids a lot of confusion with the times since in the run script the
commands are not time ordered, and raise commands can be issued at time xt but
manipulate values in the future. This makes assembling the full port values tricky
if the actions are not time ordered first. For example, for each new time value one
has to figure out what the previous status of the port is. This means one would have
to search through the full list each time, and find out what the largest time smaller
than the new time is. This is avoided in the scheme below, just one big search operation
is needed that runs very fast.

This routine easily handled 50000 steps. File sizes for a few thousand steps are
a few hundred kB, so very managable.

"""

import numpy as np


# filename = 'files\ecgroutine.txt'
filename = 'files\GetMOTGoing.txt'
# filename = 'test_batch.txt'

with open(filename) as f:
    #This reads in a batch file with tab separated columns.
    #It also automatically takes off the \n in the lines.
    #Using tap separated columnns instead of blanks is important e.g. for GPIB strings:
    #GPIB strings can contain spaces but the whole string should be one parameter.
    commandlines = f.read().splitlines()

#Helper routines
def replacebits(number,newbits,i,j):
    #Replaces bits i through j of number by newbits
    mask = (1<<(j-i+1))-1 #creates j-i+1 ones
    cleared = number & ~(mask<<i)  #shift mask into place and invert
    newbits = newbits << i #shift the new bits into place
    number = cleared | newbits  
    return number

def volts_to_dacbits(volts):
    # using 16bit int to cover range -10V to 10V
    return int(volts - (-10)/(5/16384))

def setdacbits(time,dacaddress,databits):
    #defined function for this cause this sequence is often used in all ramps
    global actionlist
    #put address bits on bus for dacs. This is action identifier 2.
    actionlist.append([time,0,2,dacaddress])
    #put the data on the databus for the dacs. This is action identifier 3.
    actionlist.append([time,0,3,databits])
    #Run the DAC trigger. Need to check how many triggers I need here!
    #For starters, just do one trigger, but might need more.
    actionlist.append( [time,dactrigger,0,0]) #just to be sure that trigger is 0 first
    actionlist.append( [time+1,dactrigger,1,0])
    actionlist.append( [time+2,dactrigger,0,0])

#Some channel definitions of hardwired channels
dacdatabits = [0,15] #16 data bits 
dactrigger = 16 
dacaddressbits = [17, 20] # 4 address bits
TTLs = [32, 95] # 4 16 bit blocks
# bonus = [21, 30]
board_sync = 31 # reserved line for board sync trigger


actionlist = []  #time, channel, actionidentifier, action parameter
#Note: Action parameters are used for dac values to avoid writing out
#too many individual TTL flips when a dacvalue or dacaddress get changed

#When encountering a GPIB command, we will store it separately 
#and then sort just the GPIB command at the end.
#Our GPIBloop VI requires a timeorderd list of times, addess string, commandstring
GPIBmatrix = []


for lines in commandlines:
    commands = lines.split('\t')
    
    if commands[0] == 'on':
        time = int(commands[1])
        channel = int(commands[2])
        actionlist.append( [time,channel,1,0]) #action 1 means set a TTL high.
        #parameter is not used for this, so set it to 0.
    
    elif commands[0] == 'off':
        time = int(commands[1])
        channel = int(commands[2])
        actionlist.append( [time,channel,0,0]) #action 0 means set a TTL low
        #parameter is not used for this, so set it to 0.
     
    elif commands[0] == 'raise':
        time = int(commands[1])
        channel = int(commands[2])
        duration = int(commands[3])
        actionlist.append( [time,channel,1,0])
        actionlist.append( [time+duration,channel,0,0])
        #parameter is not used for this, so set it to 0.

    elif commands[0] == 'dacvolts':  #dacbits xt, dacchannel, value
        time = int(commands[1])
        dacaddress = int(commands[2])
        databits =  volts_to_dacbits(float(commands[3]))
        #put this into a separate function cause used in all ramps etc.
        setdacbits(time,dacaddress,databits)
        
    elif commands[0] == 'linrampbits': #starttime, channel, startbit, endbit, duration, Nsteps
        starttime = int(commands[1])
        dacaddress = int(commands[2])
        startbit = int(commands[3])
        endbit = int(commands[4])
        duration = int(commands[5])
        Npoints = int(commands[6])
        #In loop, don't do last step cause want to do this one without rounding
        ramptimes = np.linspace(starttime, starttime+duration,Npoints-1, endpoint=False)
        rampbits = np.linspace(startbit,endbit,Npoints-1,endpoint=False)
        for tr, br in zip(ramptimes,rampbits): 
            #Don't use np.round for time: Need to avoid two things happening at same time.
            setdacbits(int(np.floor(tr)),dacaddress,int(np.round(br)))
            #print(int(np.floor(tr)), '\t', int(np.round(br)))
        #for the last step we don't want to round but be precise:
        setdacbits(starttime+duration,dacaddress,endbit)
        #print(starttime+duration, '\t', endbit)    
    
    elif commands[0] == 'GPIBwrite':
        time = int(commands[1])
        address = int(commands[2])
        Gcomms = commands[3]  #this is string! Not numbers.
        GPIBmatrix.append([time,address,Gcomms])
        

#Now that we have all actions spelled out (i.e. all individual bit settings),
#need to sort this matrix by time
actions_np = np.array(actionlist)
#Now sort the actions by the first column, which is their times
print('Sorting actions...')
actions_np = actions_np[actions_np[:, 0].argsort()]
print('Done sorting actions.') 
print(actions_np)   

#Now that everything is timeorderd, assemble all those actions that occur at a 
#given time to a final port value (all 92 bits) for that particular time.
#Action = 0: set a bit to 0
#Action = 1: set a bit to 1
#Action = 2: set dacaddressbits to the parameter value
#Action = 3: set dacdatabits to the parameter value

# Now sort the actions by the first column, which is their times
actions_np = actions_np[actions_np[:, 0].argsort()]

num_DIO_blocks = 6
uniquetimes = len(np.unique(actions_np[:,0]))
main_portlist = np.zeros((uniquetimes, num_DIO_blocks), dtype = np.uint16)
aux_portlist = np.zeros((uniquetimes, num_DIO_blocks), dtype = np.uint16)
xtlist = -1*np.ones(uniquetimes, dtype = np.uint32)
i=-1
previoustime = -1
for time, channel, action, param in actions_np:
    #Do we have a new time?
    time = int(time)
    channel = int(channel)
    #First check if this is a new time. If so, add it to xt,
    #and copy previous port state to the new time before modifying it.
    block_index = 1
    portlist = main_portlist
    if channel >= 100:
        channel -= 100
        portlist = aux_portlist
    
    block_index = channel // 16
    channel -= (block_index*16)
    if time > previoustime: #We have a new time
        i +=1
        previoustime = time
        xtlist[i] = time
        portlist[i] = portlist[i-1]
    temp = int(portlist[i][block_index])
    if action == 0:  # set a TTL to low
        portlist[i][block_index] = temp & ~(1 << channel)
    elif action == 1:  # set a TTL to high
        portlist[i][block_index] = temp | (1 << channel)
    elif action == 2:  # replace dac address bits by param
        portlist[i][block_index] = replacebits(temp, param, dacaddressbits[0], dacaddressbits[1])
    elif action == 3:  # replace dac data bits by param
        portlist[i][block_index] = replacebits(temp, param, dacdatabits[0], dacdatabits[1])
# Now we need to timeorder the GPIBmatrix
GPIBmatrix = sorted(GPIBmatrix, key=lambda x: int(x[0]))
 
'''
Now we can hand over the results to Labview.
We have for all the TTLs:
    xtlist for all the times of TTLs
    portlist as all the states of the TTLs
and for all the GPIB commands:    
    GPIBmatrix    
    
In newer Labview versions, we can use a Python node and do everything in memory.
If our Labview version does not have the Python interface, we can first
write everything into files. Even for 12000 points these files are just
a few hundred kB, so very managable.        
 '''
with open('xtlist.txt', 'w') as f:
    for line in xtlist:
        f.write(f"{line}\n")            
with open('main_portlist.txt', 'w') as f:
    for line in main_portlist:
        f.write(f"{line}\n")
with open('aux_portlist.txt', 'w') as f:
    for line in aux_portlist:
        f.write(f"{line}\n")   
with open('GPIBlist.txt', 'w') as f:
    for line in GPIBmatrix:
        f.write(f"{line[0]}\t{line[1]}\t{line[2]}\n")  
  