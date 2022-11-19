import numpy as np
from pathlib import Path
import yaml
import json

class DataHandler:
    """This class provides facilities to easily obtain physical quantities
       from raw scale/PDF variations.

       The basic assumption is that the data used for initialization is central
       result. The added data (with add_data()) is assumed to be the variations.
       The uncertainties are computed from all the data according to the
       specified method ('envelope','replicas','hessian','symhessian') by
       invoking compute_uncertainties().  Each call to compute_uncertainties
       adds a "sys_error" to all bins and fiducial cross section.
       If compute_uncertainties is not invoked result() returns the input.
    """

    def __init__(self,data):
        """Constructor.

        Initializes internal data structures.

        """
        self.raw_data = [data]
        self.result = data.copy()

    def get_result(self):
        """Return the result
        """
        return self.result

    def is_compatible(self,data):
        """Checks if the data sets are compatible
        """
        return True

    def add_data(self,data:dict):
        """Adds the result of a request to handler
        """
        if len(self.raw_data) == 0:
            self.raw_data.append(data)
            self.result = data.copy()
        elif self.is_compatible(data):
            self.raw_data.append(data)
        else:
            print("ERROR tried to combine incompatible data sets")


    def compute_sys_error(self,values:list,method:str):
        """Compute the uncertainty from provided values and return dict
           containing 'error_sys_pos' and 'error_sys_neg'
        """
        if len(values) == 0:
            return {'method':method,'pos':0.,'neg':0.}

        sys_error_pos = 0.
        sys_error_neg = 0.
        if method == 'envelope':
            central_value = values[0]
            sys_error_pos = np.amax(values)-central_value
            sys_error_neg = central_value-np.amin(values)
        elif method == 'replicas':
            central_value = values[0]
            sys_error_pos = np.sqrt(sum((np.array(values)-central_value)**2)/(len(values)-1))
            sys_error_neg = -sys_error_pos
        elif method == 'hessian':
            central_value = values[0]
            #following 0901.0002 sec 6.
            npairs = (len(values)-1)/2
            sum_diff_pos = 0.
            sum_diff_neg = 0.
            for parit in range(0,npairs):
                diff_pos = values[1+parit*2]-central_value
                diff_neg = values[1+parit*2+1]-central_value
                sum_diff_pos += (np.max([0,diff_pos,diff_neg]))**2
                sum_diff_neg += (np.max([0,-diff_pos,-diff_neg]))**2
            sys_error_pos = np.sqrt(sum_diff_pos)
            sys_error_neg = -np.sqrt(sum_diff_neg)
        elif method == 'symmhessian':
            central_value = values[0]
            #following 0901.0002 sec 6.
            npairs = len(values)-1
            sum_diff_pos = 0.
            sum_diff_neg = 0.
            for parit in range(0,npairs):
                diff_pos = values[1+parit]-central_value
                sum_diff_pos += (np.max([0,diff_pos,-diff_pos]))**2
                sum_diff_neg += (np.max([0,diff_pos,-diff_pos]))**2
            sys_error_pos = np.sqrt(sum_diff_pos)
            sys_error_neg = -np.sqrt(sum_diff_neg)
        else:
            print('method not implemented')
        return {'method':method,'pos':sys_error_pos,'neg':sys_error_neg}


    def compute_uncertainty(self,method:str):
        """Compute the uncertainty from the stored data and return dict
        """
        if len(self.raw_data) == 0 or self.result == None:
            return

        # iterate over all the histograms
        for it in range(0,len(self.result['histograms'])):
            # iteratore over all bins
            for jt in range(0,len(self.result['histograms'][it]['binning'])):
                var_values = []
                for kt in range(0,len(self.raw_data)):
                    var_values.append(self.raw_data[kt]['histograms'][it]['binning'][jt]['mean'])
                sys_error = self.compute_sys_error(var_values,method)
                if 'sys_error' in self.result['histograms'][it]['binning'][jt]:
                    self.result['histograms'][it]['binning'][jt]['sys_error'].append(
                       {'method':method,'pos':sys_error['pos'],
                                        'neg':sys_error['neg']})
                else:
                    self.result['histograms'][it]['binning'][jt]['sys_error'] = [
                       {'method':method,'pos':sys_error['pos'],
                                        'neg':sys_error['neg']}]

        var_values = []
        for kt in range(0,len(self.raw_data)):
            var_values.append(self.raw_data[kt]['fiducial_mean'])

        sys_error = self.compute_sys_error(var_values,method)
        if 'fiducial_sys_error' in self.result:
            self.result['fiducial_sys_error'].append(
                {
                    'method':method,
                    'pos':sys_error['pos'],
                    'neg':sys_error['neg']
                })
        else:
            self.result['fiducial_sys_error'] = [
                {
                    'method':method,
                    'pos':sys_error['pos'],
                    'neg':sys_error['neg']
                }]


    def SMPDFinput(self,directory:str,pdf:str,parameters={}):
        """Write data in format suitable for the SMPDF method

        It is assumed that the added data represent a full PDF variation.
        The header files contain some standard parameters which might be
        adapted by the user through the `parameter' argument.
        A directory as specified is created.

        Parameters
        ----------
        directory: str
            Path specifing the output directory.

        pdf: str
            Specify the orignal pdf

        parameters: dict
            A dict with parameters for the SMPDF input:
            - smpdf_nonlinear_corrections (bool, False)
            - smpdf_tolerance (float, 0.15)
            - order (int,2)
            - energy_scale (float,100)
        """
        Path(directory).mkdir(parents=True, exist_ok=True)

        f_bin = "{:.5g}"

        parameter_dict = {
            'smpdf_nonlinear_correction':
                parameters.get('smpdf_nonlinear_correction',False),
            'smpdf_tolerance': parameters.get('smpdf_tolerance',0.15),
            'smpdfname':pdf+'_smpdf',
            'order':parameters.get('order',2),
            'energy_scale':parameters.get('energy_scale',100.),
            'pdfsets':[pdf],
            'observables':[],
            'actions':['smpdf']
            }

        # iterate over observables (take the 0'th raw_data as reference)
        for obit, obs in enumerate(self.raw_data[0]['histograms']):
            obs_string = ''
            if 'name' in obs and obs['name'] : obs_string = obs['name']
            else:
                for it, var in enumerate(obs['variables']):
                    obs_string += var
                    if it != len(obs['variables'])-1:
                        obs_string += '_X_'

            parameter_dict['observables'].append(pdf+'_'+obs_string+'.yaml')
            obs_parameter_dict = {
                'nbins':len(obs['binning']),
                'energy_scale':parameters.get('energy_scale',100.),
                'order':parameters.get('order',2),
                'pdf_predictions':[pdf+'_'+obs_string+'.csv']
            }
            with open(directory+'/'+pdf+'_'+obs_string+'.yaml', 'w') as outfile:
                yaml.dump(obs_parameter_dict,outfile)

            with open(directory+'/'+pdf+'_'+obs_string+'.csv','w') as fpop:
                line = ''
                for it in range(0,obs_parameter_dict['nbins']):
                    line += '\t'+str(it)
                fpop.write(line+'\n')
                n_members = len(self.raw_data)
                for it in range(0,n_members):
                    line = str(it)
                    for jt in range(0,obs_parameter_dict['nbins']):
                        line += '\t'+f_bin.format(
                            self.raw_data[it]['histograms'][obit]['binning'][jt]['mean'])
                    fpop.write(line+'\n')

        with open(directory+'/'+parameter_dict['smpdfname']+'-runcard.yaml', 'w') as outfile:
            yaml.dump(parameter_dict,outfile)
