#####################################################################
#                                                                   #
# /hardware_interfaces/zaberstagecontroller.py                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the program BLACS, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

import time

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

class zaberstagecontroller(DeviceTab):
    def initialise_GUI(self):
        # Capabilities
        self.base_units = 'steps'
        self.base_min = 0
        self.base_step = 100
        self.base_decimals = 0
        
        self.device = self.settings['connection_table'].find_by_name(self.device_name)
        self.num_stages = len(self.device.child_list)
        
        # Create the AO output objects
        ao_prop = {}
        for child_name in self.device.child_list:
            stage_type = self.device.child_list[child_name].device_class
            connection = self.device.child_list[child_name].parent_port
            if stage_type == "ZaberStageTLSR150D":
                base_max = 76346
            elif stage_type == "ZaberStageTLSR300D":
                base_max = 151937
            else:
                base_max = 282879
            
            ao_prop[connection] = {'base_unit':self.base_units,
                                   'min':self.base_min,
                                   'max':base_max,
                                   'step':self.base_step,
                                   'decimals':self.base_decimals
                                  }
                                
        # Create the output objects    
        self.create_analog_outputs(ao_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Zaber Stages",ao_widgets))
        
        # Store the Measurement and Automation Explorer (MAX) name
        self.com_port = str(self.settings['connection_table'].find_by_name(self.device_name).BLACS_connection)
        
        # Set the capabilities of this device
        self.supports_remote_value_check(False)
        self.supports_smart_programming(False) 
    
    def initialise_workers(self):
        # Create and set the primary worker
        self.create_worker("main_worker",ZaberWorker,{'com_port':self.com_port})
        self.primary_worker = "main_worker"

    
class ZaberWorker(Worker):
    def init(self):
        # TODO: Make this configurable
        self.response_timeout = 45 #seconds

        global serial; import serial
        global h5py; import labscript_utils.h5_lock, h5py
        global zaberapi; import zaberapi
        
        self.connection = serial.Serial(port = self.com_port, timeout = 0.1)
        response = True
        while response is not None:
            response = zaberapi.read(self.connection)
            
    def program_manual(self,values):
        #print "***************programming static*******************"
        #self.stages.move_absolute(settings)
        for stage in values:
            port = [int(s) for s in stage.split() if s.isdigit()][0]
            zaberapi.move(self.connection,port,data=values[stage])
        t0 = time.time()
        ret = []
        while len(ret)<len(values):
            if time.time()-t0 > self.response_timeout:                
                raise Exception('Not all stages responded within %d seconds'%self.response_timeout)
            line = zaberapi.read(self.connection)
            if line is not None:
                ret.append(line)
        
        #TODO: return actual position of the zaber stage
        return values
    
    # Apparently this is not used?
    # def home_stage(self,stage):
        # zaberapi.command(self.connection,stage,'home',0)
        # t0 = time.time()
        # ret = []
        # while len(ret)<1:
            # if time.time()-t0 > self.response_timeout:                
                # raise Exception('Not all stages responded within %d seconds'%self.response_timeout)
            
            # line = zaberapi.read(self.connection)
            # if line is not None:
                # ret.append(line)
    
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        return_data = {}
        with h5py.File(h5file) as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            if 'static_values' in group:
                data = group['static_values'][:][0]
        
        for stage in data.dtype.names:
            return_data[stage] = data[stage]
            port = [int(s) for s in stage.split() if s.isdigit()][0]
            zaberapi.move(self.connection,port,data=data[stage])
        t0 = time.time()
        ret = []
        while len(ret) < len(data):
            if time.time()-t0 > self.response_timeout:                
                raise Exception('Not all stages responded within %d seconds'%self.response_timeout)
    
            line = zaberapi.read(self.connection)
            if line is not None:
                ret.append(line)
                        
        return return_data
    
    def transition_to_manual(self):
        return True
    
    def abort_buffered(self):
        return True
        
    def abort_transition_to_buffered(self):
        return True
    
    def shutdown(self):
        self.connection.close()
            
    
