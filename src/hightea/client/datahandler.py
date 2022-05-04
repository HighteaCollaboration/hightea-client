import numpy as np

class DataHandler:
    """This class provides facilities to easily obtain physical quantities from raw scale/PDF variations
    """

    def __init__(self):
        """Constructor.

        Initializes internal data structures.

        """
        self.raw_data = []
        self.new_data = None

    def is_compatible(self,data):
        """Checks if the data sets are compatible
        """
        return True

    def add_data(self,data:dict):
        """Adds the result of a request to handler
        """
        if len(self.raw_data) == 0:
            self.raw_data.append(data)
        elif self.is_compatible(data):
            self.raw_data.append(data)
        else:
            print("ERROR tried to combine incompatible data sets")


    def compute_sys_error(self,values:list,method:str):
        """Compute the uncertainty from provided values and return dict
           containing 'error_sys_pos' and 'error_sys_neg'
        """
        if len(values) == 0:
            return {'sys_error_pos':0.,'sys_error_neg':0.}

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
                diff_neg = values[1+parit*2+1]-centra_value
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
        return {'sys_error_pos':sys_error_pos,
                'sys_error_neg':sys_error_neg}

    def compute_uncertainty(self,method:str):
        """Compute the uncertainty from the stored data and return dict
        """
        if len(self.raw_data) == 0:
            return

        # iterate over all the histograms
        for it in range(0,len(self.raw_data[0]['histograms'])):
            # iteratore over all bins
            for jt in range(0,len(self.raw_data[0]['histograms'][it])):
                var_values = []
                for kt in range(0,len(self.raw_data)):
                    var_values.append(self.raw_data[kt]['histograms'][it][jt]['mean'])
                sys_error = self.compute_sys_error(var_values,method)
                if 'sys_error' in self.raw_data[0]['histograms'][it][jt]:
                    self.raw_data[0]['histograms'][it][jt]['sys_error'].append(
                       {'method':method,'pos':sys_error['sys_error_pos'],
                                        'neg':sys_error['sys_error_neg']})
                else:
                    self.raw_data[0]['histograms'][it][jt]['sys_error'] = [
                       {'method':method,'pos':sys_error['sys_error_pos'],
                                        'neg':sys_error['sys_error_neg']}]

        var_values = []
        for kt in range(0,len(self.raw_data)):
            var_values.append(self.raw_data[kt]['fiducial_mean'])

        sys_error = self.compute_sys_error(var_values,method)
        if 'fiducial_sys_error' in self.raw_data[0]:
            self.raw_data[0]['fiducial_sys_error'].append(
                {
                    'method':method,
                    'pos':sys_error['sys_error_pos'],
                    'neg':sys_error['sys_error_neg']
                })
        else:
            self.raw_data[0]['fiducial_sys_error'] = [
                {
                    'method':method,
                    'pos':sys_error['sys_error_pos'],
                    'neg':sys_error['sys_error_neg']
                }]
