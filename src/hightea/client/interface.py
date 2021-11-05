import json
from .apiactions import API
import numpy as np
from datetime import datetime
import time

#FIBO = [1, 1, 2, 3, 5, 8, 13, 21]
FIBO = [10,10]
def saturate(it):
    for val in it:
        yield val
    while True:
        yield val
# TODOs
#define standard behaviour for print()
#define export routines to YODA,yaml,csv,JSON
#implement variable load from file

class Interface:
    ###########################################################################
    # 'constructor'                                                           #
    ###########################################################################
    api = None
    histograms = {}
    proc = ''
    metadata = {}
    valid_contributions = []
    custom_variables = {}

    def __init__(self):
        self.api = API()
        self.histograms = {0:{'json':{'name':'default'}}}
        self.proc = ''
        self.metadata = {}
        self.valid_contributions = []
        self.custom_variables = {}

    ###########################################################################
    # internal member functions                                               #
    ###########################################################################

    def print_metadata(self, proc, metadata):
        """
        Nicely formatted metadata printout
        """
        print('  ',metadata['name'],'\n')
        print('Process tag       : ',proc.replace('processes/',''),
              ' (use for process specification)')
        print('Default scales    : ',metadata['scales_info'])
        print('Default pdf       : ',metadata['pdf_set'],'/',
              metadata['pdf_member'])
        print('Contributions     : ',
              list(metadata['contribution_groups'].keys()))
        print('Predefined variables')
        for var in metadata['variables'].keys():
            print('  ','{0: <10}'.format(var),' : ',metadata['variables'][var])


    def compile_variations(self,hid):
        """
        Checks if histogram hid has a variation request and if yes
        compiles the list of required scale/pdf choices
        """
        if not 'variation' in self.histograms[hid]:
            return True;

        mur = 'muR0'
        muf = 'muF0'
        pdf = self.metadata['pdf_set']
        if 'muR' in self.histograms[hid]['json']:
            mur = self.histograms[hid]['json']['muR']
        if 'muF' in self.histograms[hid]['json']:
            muf = self.histograms[hid]['json']['muF']
        if 'pdf' in self.histograms[hid]['json']:
            pdf = self.histograms[hid]['json']['pdf']

        list_of_setups = [mur+','+muf+','+pdf]
        for var in self.histograms[hid]['variation']:
            if var == '3-point':
                list_of_setups.append(mur+'*2,'+muf+'*2,'+pdf)
                list_of_setups.append(mur+'/2,'+muf+'/2,'+pdf)
            if var == '7-point':
                list_of_setups.append(mur+'*2,'+muf+'*2,'+pdf)
                list_of_setups.append(mur+'/2,'+muf+'/2,'+pdf)
                list_of_setups.append(mur+','+muf+'*2,'+pdf)
                list_of_setups.append(mur+','+muf+'/2,'+pdf)
                list_of_setups.append(mur+'*2,'+muf+','+pdf)
                list_of_setups.append(mur+'/2,'+muf+','+pdf)

        self.histograms[hid]['json']['variation'] = list_of_setups
        return True;


    ###########################################################################
    # internal checks                                                         #
    ###########################################################################

    def is_valid_contribution(self, con):
        """
        Return true if con is a correct contribution.
        """
        if con in self.valid_contributions:
            return True
        else:
            return False

    def is_valid_bin_spec(self, bin_spec):
        """
        Return true if bin is correct 1D bin specification.
        """
        if type(bin_spec) == dict and 'variable' in bin_spec and 'bins' in bin_spec:
            return True
        else:
            return False

    def is_valid_process(self, proc):
        """
        Return true if proc is a string
        """
        if type(proc) == str:
            return True
        else:
            return False

    def is_valid_cut(self, cut):
        """
        Return true if cut is a valid cut
        """
        if type(cut) == str:
            return True;
        else:
            return False;


    ###########################################################################
    # simple database interactions                                            #
    ###########################################################################

    def list_processes(self, detailed=True):
        """
        Request the list of available processes from the server
        """
        processes = self.api.list_processes()
        for proc in processes:
            if proc != 'processes/tests':
                if detailed:
                    print('#############################################\n')
                    metadata = self.api.simple_req('get',proc)
                    self.print_metadata(proc,metadata)
                    print('\n')
                else:
                    print(proc.replace('processes/',''))


    def list_pdfs(self):
        """
        Request the list of available pdfs from the server
        """
        pdfs = self.api.list_pdfs()
        for pdf in pdfs: print(pdf)


    ###########################################################################
    # job interactions                                                        #
    ###########################################################################

    def start(self):
        """
        The first routine to be called. Note: it wipes all data stored
        """
        self.clear()


    def clear(self):
        """
        Restore default state
        """
        self.histograms = {0:{'json':{'name':'default'}}}
        self.proc = ''
        self.metadata = {}


    def process(self, proc:str, verbose=True):
        """
        Define process for this job. A request to the server is performed and
        the process' metadata is stored and printed.
        """
        if self.is_valid_process(proc):
            self.proc = 'processes/'+proc
            self.metadata = self.api.simple_req('get',self.proc)
            if verbose: self.print_metadata(self.proc,self.metadata)
            self.valid_contributions = list(self.metadata['contribution_groups'].keys())
        else:
            print('WARNING: process(proc)')
            print(' -> specified proc not in the correct format (string).')
            print(' -> Nothing has been changed.')


    def define_new_variable(self, name:str, definition:str, hid=0):
        """
        Allows to define a new variable. The definition has to be a python expression
        using pre defined variables, see process meta data for additional information.
        """
        self.custom_variables[name] = definition


    def add_histogram(self, json=None):
        """
        Add an inpendent histogram to the job. The routine will return the
        histogram hid which can be used to modify specifications.
        """
        new_id = len(self.histograms)
        if json == None:
            self.histograms[new_id] = {'json':{'name':'default'}}
        elif type(json) == dict:
            self.histograms[new_id] = {'json':json}
        elif type(json) == str:
            self.histograms[new_id] = {'json':json.load(json)}
        else:
            print('WARNING: add_histogram(json=None)')
            print(' -> Input not reconised, either input is a filepath or dict.')
            print(' -> Nothing changed.')
            return -1;

        if 'name' in self.histograms[new_id]['json']:
            return new_id
        else:
           self.histograms[new_id]['json']['name'] = 'default'
           return new_id


    def request(self,hid=-1):
        """
        Submit request to database and wait for the answer. The answer
        is stored and can be returned by result()
        """

        ids = []
        if hid == -1:
            ids = self.histograms.keys()
        elif type(hid) == int:
            ids = [hid]
        elif type(hid) == list:
            ids = hid

        # first check if all histograms have a process specified
        # and compile the variation list if requested.
        for it in ids:
            self.compile_variations(it)
            self.histograms[it]['json']['custom_variables'] = self.custom_variables

        # submit all processes
        for it in ids:
            json = self.histograms[it]['json']
            resp = self.api.simple_req('post',
                                       self.proc+'/hist',
                                       data=json)
            self.histograms[it]['token'] = resp['token']
            self.histograms[it]['result'] = 'submitted'

        print('request submitted : ',datetime.now())
        for timeout in saturate(FIBO):
            is_waiting = False
            for it in ids:
                if self.histograms[it]['result'] == 'submitted':
                    token = self.histograms[it]['token']
                    resp = self.api.simple_req('get',f'token/'+token+'/status')['status']
                    if resp == 'completed':
                        self.histograms[it]['result'] =  self.api.simple_req('get',f'token/'+token+'/result')
                    elif resp == 'errored':
                        print('error occured    : ',datetime.now())
                        self.histograms[it]['result'] = 'error'
                    else:
                        is_waiting = True;
            if is_waiting == True:
                time.sleep(timeout)
            else:
              print('request finished  : ',datetime.now())
              return


    def get_histograms(self):
        """
        Return the stored histograms, this includes not only the request but
        also the results in raw format
        """
        return self.histograms.copy()


    def result(self,hid=0):
        """
        Return the result of a request
        """
        if 'result' in self.histograms[hid]:
            output = self.histograms[hid]['result']
            output['info'] = self.histograms[hid]['json']
            return output
        else:
            print("WARNING: result not available")
            return False


    def results(self):
        """
        Return the result of all request
        """
        output = []
        for it in self.histograms.keys():
            if 'result' in self.histograms[it]:
                cur = self.histograms[it]['result']
                cur['info'] = self.histograms[it]['json']
                output.append(cur)
            else:
                print("WARNING: result not available")
                return False
        return output

    ###########################################################################
    # histogram interactions                                                  #
    ###########################################################################

    def description(self, name:str, hid=0):
        """
        Add a description to a histogram, this name can be used to easily organize
        your results.
        """
        self.histograms[hid]['json']['name'] = name


    def contribution(self, con, hid=0):
        """
        Define contributions for histogram hid (=0), the input is either a string
        or a list of strings.
        """
        success = True
        if type(con) == list:
            for e in con:
                if self.is_valid_contribution(e) == False:
                    success = False
            if success:
                self.histograms[hid]['json']['contributions'] = con
        elif type(con) == str and self.is_valid_contribution(con):
            self.histograms[hid]['json']['contributions'] = [con]
        else:
            success = False

        if success == False:
            print('WARNING: contributions(con,hid)')
            print(' -> con has to be a single string or a list of strings.')
            print(' -> Histogram '+str(hid)+' has not been changed')


    def binning(self, binning, hid=0):
        """
        Define the binning for histogram hid (=0), the input is either a single
        dictionary (1D histogram) or a list of dictionaries (multi-dimensional
        histogram). Each dict is check to have at least the "variable" and "bins"
        key words.
        """
        success = True
        if type(binning) == list:
            for e in binning:
                if self.is_valid_bin_spec(e) == False:
                    success = False
            if success:
                self.histograms[hid]['json']['binning'] = binning
        elif self.is_valid_bin_spec(binning):
            self.histograms[hid]['json']['binning'] = [binning]
        else:
            success = False

        if success == False:
            print('WARNING: binning(binning,hid)')
            print(' -> binning has to be a single bin specification or a list.')
            print(' -> Histogram '+str(hid)+' has not been changed')


    def binning(self, variable:str, binning:list, hid=0):
        """
        Add a binning in variable (string) with specified bins (list)
        """
        new_bin_spec = {'variable':variable,'bins':binning}
        if 'binning' in self.histograms[hid]['json']:
            self.histograms[hid]['json']['binning'].append(new_bin_spec)
        else:
            self.histograms[hid]['json']['binning'] = [new_bin_spec]


    def scales(self, muR:str, muF:str, hid=0):
        """
        Define the central choice for the renormalization (muR) and
        factorization (muF) scale
        """
        self.histograms[hid]['json']['muR'] = muR
        self.histograms[hid]['json']['muF'] = muF


    def pdf(self, pdf:str, hid=0):
        """
        Define the central choice for the renormalization (muR) and
        factorization (muF) scale
        """
        self.histograms[hid]['json']['pdf'] = pdf

    def scale_variation(self, variation_type:str, hid=0):
        """
        Specify the type of scale variations:
          '3-point': 3-point variation around central scales
          '7-point': 7-point variation around central scales
        More individual type of variations can be specified via set_custom_variation
        """
        if variation_type == '3-point' or variation_type == '7-point':
            if 'variation' in self.histograms[hid]:
                self.histograms[hid]['variation'].append(variation_type)
            else:
                self.histograms[hid]['variation'] = [variation_type]

    def pdf_variation(self, variation_type:str, hid=0):
        """
        Specify the type of pdf variation:
        'standard': Full pdf member variation to determine pdf uncertainties as
                    specified by pdf set. NOTE: This might be time consuming as
                    it corresponds to O(100) reweight setups.
        'reduced' : For many available pdf sets a reduced member set has been
                    produced within the SMPDF formalism (CITE). This allows for
                    faster pdf uncertainty estimatation (O(10) reweight setups).
                    This approach typically reproduces 'standard' pdf uncertainty
                    up to O(1%) accuracy.
        """
        if variation_type == 'standard' or variation_type == 'reduced':
            if 'variation' in self.histograms[hid]:
                self.histograms[hid]['variation'].append(variation_type)
            else:
                self.histograms[hid]['variation'] = [variation_type]


    def cuts(self, cuts, hid=0):
        """
        Specify phase space cuts. This allows to contrain the phase space of the
        requested process. For processes which required generation cuts, the user
        cuts have to be more exclusive then the generation cuts. If there are not
        the result will be correct for combined cuts, generation and user cuts,
        only (which may render the user cuts irrelevant). With other words the
        generation cuts are **always** applied on top of the user cuts.
        """
        if type(cuts) == str:
            if self.is_valid_cut(cuts):
                if 'cuts' in self.histograms[hid]['json']:
                    self.histograms[hid]['json']['cuts'].append(cuts)
                else:
                    self.histograms[hid]['json']['cuts'] = [cuts]
            else:
                print("WARNING: "+cuts+" is not a valid cut, will be ignored.")
        elif type(cuts) == list:
            for cut in cuts:
                if self.is_valid_cut(cut):
                    if 'cuts' in self.histograms[hid]['json']:
                        self.histograms[hid]['json']['cuts'].append(cut)
                    else:
                        self.histograms[hid]['json']['cuts'] = [cut]
                else:
                    print("WARNING: "+cut+" is not a valid cut, will be ignored.")
        else:
            print("WARNING: "+cut+" is not a valid cut, will be ignored.")


    def show_result(self,hid=0):
        """
        Print the result in a human readable form to the standard output
        """
        if 'result' in self.histograms[hid]:
            json = self.histograms[hid]['json']
            res  = self.histograms[hid]['result']
            print('Name          : ',json['name'])
            print('Contributions : ',json['contributions'])
            if 'muR' in json:
                print('muR           : ',json['muR'])
            if 'muF' in json:
                print('muF           : ',json['muF'])
            if 'pdf' in json:
                print('pdf           : ',json['pdf'])
            if 'variation' in self.histograms[hid]:
                print('variation     : ',self.histograms[hid]['variation'])
            print('Histogram     :\n')
            dimension = len(json['binning'])
            f_bin = "{0:9.5g}"
            f_xsec = "{0:11.5g}"
            f_var  = "{0:10.2g}"
            header = ''
            for it in range(0,dimension):
                header += ' bin'+str(it+1)+' low  |'
                header += ' bin'+str(it+1)+' high |'
            header += ' sigma [pb]  | mc-err [pb] |'
            if 'variation' in self.histograms[hid]:
                if '3-point' in self.histograms[hid]['variation']:
                    header += ' scale-unc.(3-point) [%] |'
                if '7-point' in self.histograms[hid]['variation']:
                    header += ' scale-unc.(7-point) [%] |'
                if 'standard' in self.histograms[hid]['variation']:
                    header += ' pdf-unc.(standard) [%]  |'
                if 'reduced' in self.histograms[hid]['variation']:
                    header += ' pdf-unc.(reduced) [%]   |'
            print(header)
            means = res['mean']
            stds  = res['std']
            length = len(means)
            for binit in range(0,length):
                line = ''
                for it in range(0,dimension):
                    line += ' '+f_bin.format(means[binit][0][it][0])+' |'
                    line += ' '+f_bin.format(means[binit][0][it][1])+' |'
                line += ' '+f_xsec.format(means[binit][1][0])+' |'
                line += ' '+f_xsec.format(stds[binit][1][0])+' |'
                if 'variation' in self.histograms[hid]:
                    if '3-point' in self.histograms[hid]['variation']:
                        scale_ce = means[binit][1][0]
                        scale_up = np.amax(means[binit][1])
                        scale_do = np.amin(means[binit][1])
                        line += ' +'+f_var.format((scale_up-scale_ce)/scale_ce*100.)+\
                               '/ -'+f_var.format((scale_ce-scale_do)/scale_ce*100.)+'|'
                    if '7-point' in self.histograms[hid]['variation']:
                        header += '| scale-unc.(7-point) [%] |'
                    if 'standard' in self.histograms[hid]['variation']:
                        header += '| pdf-unc.(standard) [%]  |'
                    if 'reduced' in self.histograms[hid]['variation']:
                        header += '| pdf-unc.(reduced) [%]   |'
                print(line)
            print('\n')

        else:
            print("WARNING: result not available")
            return False

    ###########################################################################
    # file operations                                                         #
    ###########################################################################

    def read_json(self,filename,hid=0):
        """
        Read in histogram specification from json file
        """
        self.histograms[hid]['json'] = json.load(filename)


    def write_json(self,filename,hid=0):
        """
        Write histogram to specified file in json format
        """
        with open(filename,'w') as fp:
            json.dump(self.histograms[hid]['json'],fp,indent=2)
