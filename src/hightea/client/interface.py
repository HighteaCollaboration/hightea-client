import json
import time
from pathlib import Path
from datetime import datetime
import os
import numpy as np

from .apiactions import API,FIBO,saturate
from .datahandler import DataHandler

class Interface:
    """High-level user interface to the HighTEA database

    Examples
    --------
    >>> job = hightea('jobname')
    >>> job.process('pp_ttx_13TeV')
    >>> job.contribution('LO')
    >>> job.binning('pt_top',[0.,50.,100.,150.,200.,250.])
    >>> job.request()
    >>> job.show_result()
    """

    def __init__(self,name:str ,directory='.', overwrite=False):
        """Constructor, requires job name.

        If job already exists, job is loaded from the drive.

        Parameters
        ----------
        name: str
            Specifies a job name which needs to be unique. The job's data is
            stored in directory/<name>.job .

        directory: str, default .
            Specification of the directory containing job files.
            If not existing the directory is created.

        overwrite: bool, default False
            If `True` existing job data is overwritten.

        """
        self.api = API()
        self.name = name
        self.directory = directory
        # create directory in case it doesn't exist
        Path(directory).mkdir(parents=True, exist_ok=True)
        Path(directory+'/hightea-jobs/').mkdir(parents=True, exist_ok=True)
        self.filename = directory+'/hightea-jobs/'+name+'.job'

        if Path(self.filename).is_file() and not overwrite:
            print("Load data from :",self.filename)
            jsonfile = {}
            with open(self.filename,'r') as fp:
                jsonfile = json.load(fp)
            self.proc = jsonfile['proc']
            self.valid_contributions = jsonfile['valid_contributions']
            self.custom_variables = jsonfile['custom_variables']
            self.variation_info = jsonfile['variation_info']
            self.variations = jsonfile['variations']
            self.requests = jsonfile['requests']
            self.status = jsonfile['status']
            self.metadata = self.api.simple_req('get',self.proc)
        else:
            if overwrite and Path(self.filename).is_file():
                print("Remove data from :",self.filename)
                os.remove(self.filename)
            self.proc = ''
            self.metadata = {}
            self.valid_contributions = []
            self.custom_variables = {}
            self.variation_info = []
            self.variations = []
            self.requests = [{'json':{'observables':[]},
                              'token':None,'status':None,'result':None}]
            self.status = 'preparation'
            self.store()


    ###########################################################################
    # internal member functions                                               #
    ###########################################################################

    def _print_metadata(self, proc, metadata):
        """Nicely formatted metadata printout
        """
        print('  ',metadata['name'],'\n')
        print('Process tag          : ',proc.replace('processes/',''),
              ' (use for process specification)')
        print('Default scales      : ',metadata['scales_info'])
        print('Default pdf         : ',metadata['pdf_set'],'/',
              metadata['pdf_member'])
        print('Avail. contributions: ',
              list(metadata.get('contribution_groups',{}).keys()))
        print('Predefined variables')
        for var in metadata['variables'].keys():
            print('  ','{0: <10}'.format(var),' : ',metadata['variables'][var])


    def _finalize_request(self):
        """Checks and finalize a request before submitting
        """
        self.requests[0]['json']['custom_variables'] = self.custom_variables
        self._compile_variations()


    def _compile_variations(self):
        """Compile variations if requested.

        Checks if a variation is requested and if yes compiles a
        list of individual scale/pdf choices to be computed.
        """
        if len(self.variation_info) == 0:
            return True;

        mur = 'muR0'
        muf = 'muF0'
        pdf = self.metadata['pdf_set']
        pdf_member = self.metadata['pdf_member']
        if 'muR' in self.requests[0]['json']:
            mur = self.requests[0]['json']['muR']
        if 'muF' in self.requests[0]['json']:
            muf = self.requests[0]['json']['muF']
        if 'pdf' in self.requests[0]['json']:
            pdf = self.requests[0]['json']['pdf']
        if 'pdf_member' in self.requests[0]['json']:
            pdf_member = self.requests[0]['json']['pdf_member']

        list_of_setups = [mur+','+muf+','+pdf+','+str(pdf_member)]
        for var in self.variation_info:
            if var['type'] == 'scale':
                if var['nvar'] == 3:
                    list_of_setups.append(mur+'*2,'+muf+'*2,'+pdf+','+str(pdf_member))
                    list_of_setups.append(mur+'/2,'+muf+'/2,'+pdf+','+str(pdf_member))
                if var['nvar'] == 7:
                    list_of_setups.append(mur+'*2,'+muf+'*2,'+pdf+','+str(pdf_member))
                    list_of_setups.append(mur+'/2,'+muf+'/2,'+pdf+','+str(pdf_member))
                    list_of_setups.append(mur+','+muf+'*2,'+pdf+','+str(pdf_member))
                    list_of_setups.append(mur+','+muf+'/2,'+pdf+','+str(pdf_member))
                    list_of_setups.append(mur+'*2,'+muf+','+pdf+','+str(pdf_member))
                    list_of_setups.append(mur+'/2,'+muf+','+pdf+','+str(pdf_member))

            if var['type'] == 'pdf - smpdf' or var['type'] == 'pdf - full':
                cur_pdf = pdf
                if var['type'] == 'pdf - smpdf' and cur_pdf.find('smpdf') == -1:
                    pdf_smpdf = cur_pdf+'_'+self.proc.replace('processes/','')+'_smpdf'
                    if pdf_smpdf in self.metadata['available_pdfs']:
                        cur_pdf = pdf_smpdf

                if self.metadata['available_pdfs'][cur_pdf]['error_method'] == 'none':
                    print('No PDF variation available for PDF set: '+cur_pdf)
                else:
                    nmembers = self.metadata['available_pdfs'][cur_pdf]['nmembers']
                    var['nvar'] = nmembers
                    var['error_method'] = self.metadata['available_pdfs'][cur_pdf]['error_method']
                    for it in range(1,nmembers):
                        list_of_setups.append(mur+','+muf+','+cur_pdf+','+str(it))

            if var['type'] == 'custom':
                for setup in var['custom_list']:
                    list_of_setups.append(setup)

        self.variations = list_of_setups

        for setup in list_of_setups[1:]:
            js = self.requests[0]['json'].copy()
            muRval, muFval, pdfval, pdfmval = setup.split(',')
            js['muR'] = muRval
            js['muF'] = muFval
            js['pdf'] = pdfval
            js['pdf_member'] = pdfmval
            self.requests.append({'json':js.copy()})

        return True;


    def _finalize_result(self):
        """Finalized the results, i.e. computes systematic uncertainties.
        """

        self.requests[0]['result']['info']['name'] = self.name

        count = 1;
        # do one variation at a time
        for var_info in self.variation_info:
            comb = DataHandler();
            # the assumption is that the first request is always the
            # central prediction
            comb.add_data(self.requests[0]['result'])
            for reqit in range(1,var_info['nvar']):
                comb.add_data(self.requests[count]['result'])
                count += 1
            comb.compute_uncertainty(var_info['error_method'])
        self.store()


    ###########################################################################
    # internal checks                                                         #
    ###########################################################################

    def _is_valid_contribution(self, con):
        """Return true if con is a correct contribution.
        """
        if con in self.valid_contributions:
            return True
        else:
            return False


    def _is_valid_bin_spec(self, bin_spec):
        """Return true if bin is correct 1D bin specification.
        """
        if type(bin_spec) == dict and 'variable' in bin_spec and 'bins' in bin_spec:
            return True
        else:
            return False


    def _is_valid_process(self, proc):
        """Return true if proc is a string
        """
        if type(proc) == str:
            return True
        else:
            return False


    def _is_valid_cut(self, cut):
        """Return true if cut is a valid cut
        """
        if type(cut) == str:
            return True;
        else:
            return False;


    ###########################################################################
    # simple database interactions                                            #
    ###########################################################################

    def list_processes(self, detailed=True):
        """Request the list of available processes from the server

        Parameters
        ----------
        detailed: bool, default True
            If `True` detailed information for each process is provided, if
            `False` only the process key is shown.
        """
        processes = self.api.list_processes()
        for proc in processes:
            if proc != 'processes/tests':
                if detailed:
                    print('#############################################\n')
                    metadata = self.api.simple_req('get',proc)
                    self._print_metadata(proc,metadata)
                    print('\n')
                else:
                    print(proc.replace('processes/',''))


    def list_pdfs(self):
        """Request the list of available pdfs from the server
        """
        pdfs = self.api.list_pdfs()
        for pdf in pdfs: print(pdf)


    ###########################################################################
    # job interactions                                                        #
    ###########################################################################

    def process(self, proc:str, verbose=True):
        """Define process for this instance.
        A request to the server is performed and the process' metadata is
        stored.

        Parameters
        ----------
        proc: str
            String containing the process key.
        verbose: bool, default True
            If `True` the process information is printed.
        """
        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if self._is_valid_process(proc):
            self.proc = 'processes/'+proc
            self.metadata = self.api.simple_req('get',self.proc)
            if verbose: self._print_metadata(self.proc,self.metadata)
            self.valid_contributions = list(self.metadata.get('contribution_groups',{}).keys())

        else:
            # TODO: how to implement properly warnings
            print('WARNING: process(proc)')
            print(' -> specified proc not in the correct format (string).')
            print(' -> Nothing has been changed.')
        self.store()


    def define_new_variable(self, name:str, definition:str):
        """Define new variable
        The definition has to be a python expression using pre-defined variables,
        see process meta data for additional information.

        Parameters
        ----------
        name: str
            A name for the new variable
        definition: str
            The definition can be given in terms of mathematical functions of the
            already defined variables. Expressions are written using the
            conventions of the Python language.
        """
        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self.custom_variables[name] = definition
        self.store()


    def load_variable_definitions(self, filename:str):
        """Load variable definitions from file.

        The specified file is expected to be json dictionary of
        ``"name":"definition"`` pairs.

        Parameters
        ----------
        filename: str
            The filename containing the definitions.
        """
        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        with open(filename,'r') as fp:
            new_variables = json.load(fp)
            for key in new_variables.keys():
                if not type(new_variables[key]) == str:
                    print('WARNING: Definition not a string. Not added.')
                else:
                    self.custom_variables[key] = new_variables[key]


    def add_variable_definitions(self, definitions:dict):
        """Add variable definitions from dictionary.

        The specified to be a dictionary of ``"name":"definition"`` pairs.

        Parameters
        ----------
        definitions: dict
            The dictionary containing the definitions.
        """
        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        for key in definitions.keys():
            if not type(definitions[key]) == str:
                print('WARNING: Definition not a string. Not added.')
            else:
                self.custom_variables[key] = definitions[key]


    def store_variable_definitions(self, filename:str):
        """Store variable definitions to file.

        Parameters
        ----------
        filename: str
            The filename containing the definitions.
        """
        with open(filename,'w') as fp:
            json.dump(self.custom_variables,fp,indent=2)


    def request(self):
        """Create and submit requests for all defined histograms and wait for the answer.
        The results is stored.
        """
        self.submit_request()
        for timeout in saturate(FIBO):
            if self.request_result():
                print('request finished  : ',datetime.now())
                return
            else:
                time.sleep(timeout)


    def submit_request(self):
        """Submit request to database but don't wait for the answer.
        The answer can be received via request_result().
        """

        if len(self.requests) > 0:
            if self.requests[0]['token'] != None:
                print('WARNING: job already submitted. Nothing submitted.')
                return
        else:
            print('WARNING: job does not contain requests. Nothing submitted.')
            return

        self._finalize_request()

        ids = list(range(0,len(self.requests)))

        # submit all requests
        for it in ids:
            resp = self.api.simple_req('post',
                                       self.proc+'/multi_hist',
                                       data=self.requests[it]['json'])
            self.requests[it]['token'] = resp['token']
            self.requests[it]['status'] = 'submitted'

        self.status = 'submitted'
        print('request submitted : ',datetime.now())
        self.store()


    def request_result(self):
        """Request the results for submitted request.
        If all tokens have been completed the function returns true
        otherwise false.

        Returns
        -------
        finished: bool
            If all requested tokens have been completed the return value is `True`,
            `False` otherwise.
        """

        if self.status == 'finished': return True

        ids = list(range(0,len(self.requests)))

        finished = True
        for jt, req in enumerate(self.requests):
            if req['status'] == 'submitted':
                resp = self.api.simple_req('get',f'token/'+req['token'])
                if resp['status'] == 'completed':
                    self.requests[jt]['result'] = json.loads(resp['result'])
                    self.requests[jt]['status'] = 'completed'
                elif resp == 'errored':
                    print('error occured    : ',datetime.now())
                    self.requests[it]['status'] = 'errored'
                else:
                    finished = False;

        self.store()
        if finished:
            self._finalize_result()
            self.status = 'finished'
        return finished


    def get_requests(self):
        """Return the stored requests
        This includes not only the request but also the results in raw format

        Notes
        -----
        This routine is meant for debugging and troubleshooting.
        """
        return self.requests.copy()


    def result(self):
        """Return the results of a request taking into account
           systematic uncertainties from requested variations.

        The returned dictionary can be used within the hightea-plotting
        routines.

        Returns
        -------
        result: dict
            A dictionary containing the results.
        """

        if self.status != 'finished':
            print('WARNING: job not finished, no results available')
            return

        return self.requests[0]['result']


    def show_result(self):
        """Print the result in a human readable form
        """
        res = self.result()
        info = self.requests[0]['json']

        f_bin = "{0:9.5g}"
        f_xsec = "{0:11.5g}"
        f_var  = "{0:9.2g}"

        print('Name                    : ',self.name)
        print('Contributions           : ',info['contributions'])
        if 'muR' in info:
            print('muR                     : ',info['muR'])
        if 'muF' in info:
            print('muF                     : ',info['muF'])
        if 'pdf' in info:
            print('pdf                     : ',info['pdf'])

        print('fiducial xsection       : ',f_xsec.format(res['fiducial_mean']))
        print('fiducial xsection error : ',f_xsec.format(res['fiducial_error']))

        for it, var_info in enumerate(self.variation_info):
            print('systematic unc. [%]     : '+var_info['type']+' ('+str(var_info['nvar'])+')')
            var_ce = res['fiducial_mean']
            var_up = res['fiducial_sys_error'][it]['pos']
            var_do = res['fiducial_sys_error'][it]['neg']
            print('                        : '+\
                  ' +'+f_var.format((var_up)/var_ce*100.)+\
                  '/ -'+f_var.format((var_do)/var_ce*100.))

        # compute and print histograms
        for it, histo in enumerate(res['histograms']):

            dimension = len(info['observables'][it])

            variable_str = ''
            for jt in range(0,dimension):
                if jt == 0:
                    variable_str += info['observables'][it][jt]['variable']
                else:
                    variable_str += ' x '+info['observables'][it][jt]['variable']

            print('Histogram     :',variable_str)
            header = ''
            for jt in range(0,dimension):
                header += ' bin'+str(jt+1)+' low  |'
                header += ' bin'+str(jt+1)+' high |'
            header += ' sigma [pb]  | mc-err [pb] |'
            for jt, var_info in enumerate(self.variation_info):
                header += (' '+var_info['type']+' ('+str(var_info['nvar'])+')'+' [%] |').rjust(24)

            print(header)
            length = len(histo)
            for binit in range(0,length):
                line = ''
                # bins
                for it in range(0,dimension):
                    line += ' '+f_bin.format(histo[binit]['edges'][it]['min_value'])+' |'
                    line += ' '+f_bin.format(histo[binit]['edges'][it]['max_value'])+' |'

                line += ' '+f_xsec.format(histo[binit]['mean'])+' |'
                line += ' '+f_xsec.format(histo[binit]['error'])+' |'
                for jt, var_info in enumerate(self.variation_info):
                    var_ce = histo[binit]['mean']
                    var_up = histo[binit]['sys_error'][jt]['pos']
                    var_do = histo[binit]['sys_error'][jt]['neg']
                    line += ' +'+f_var.format((var_up)/var_ce*100.)+\
                           '/ -'+f_var.format((var_do)/var_ce*100.)+'|'
                print(line)
            print('\n')


    ###########################################################################
    # histogram interactions                                                  #
    ###########################################################################

    def contribution(self, con):
        """Define contribution(s) for histogram.

        Parameters
        ----------
        con: str or list(str)
            A string (or list of strings) defining the contribution(s)
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        success = True
        if type(con) == list:
            for e in con:
                if self._is_valid_contribution(e) == False:
                    success = False
            if success:
                self.requests[0]['json']['contributions'] = con
        elif type(con) == str and self._is_valid_contribution(con):
            self.requests[0]['json']['contributions'] = [con]
        else:
            success = False

        if success == False:
            print('WARNING: contributions(con)')
            print(' -> con has to be a single string or a list of strings.')
            print(' -> Nothing has been changed.')

        self.store()


    def binning(self, binning):
        """Define the binning for histogram via dictionaries.

        Each dict is check to have at least the "variable" and "bins" key words.

        Parameters
        ----------
        binning: dict or list(dict)
            A dict (or list of dicts) defining the binning(s)
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        success = True
        if type(binning) == list:
            for e in binning:
                if self._is_valid_bin_spec(e) == False:
                    success = False
            if success:
                self.requests[0]['json']['observables'].append(binning)
        elif self._is_valid_bin_spec(binning):
            self.requests[0]['json']['observables'].append([binning])
        else:
            success = False

        if success == False:
            print('WARNING: binning(binning)')
            print(' -> binning has to be a single bin specification or a list.')

        self.store()


    def binning(self, variable:str, binning:list):
        """Add a binning in variable (string) with specified bins (list)

        Parameters
        ----------
        variable: str
            The variable to be binned.
        binning: list(float)
            A list of bin edges.
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        new_bin_spec = {'variable':variable,'bins':binning}
        self.requests[0]['json']['observables'].append([new_bin_spec])
        self.store()


    def scales(self, muR:str, muF:str):
        """Define the central scale choices
        Define the central choice for the renormalization (muR) and
        factorization (muF) scale

        Parameters
        ----------
        muR: str
            Expression to define muR.
        muF: str
            Expression to define muF.
        """
        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self.requests[0]['json']['muR'] = muR
        self.requests[0]['json']['muF'] = muF
        self.store()


    def pdf(self, pdf:str, pdf_member=0):
        """Define the pdf

        Parameters
        ----------
        pdf: str
            PDF name (refer to :py:func:`Interface.list_pdfs()`).

        pdf_member: int, default 0
            Specify PDF member
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self.requests[0]['json']['pdf'] = pdf
        self.requests[0]['json']['pdf_member'] = pdf_member
        self.store()


    def scale_variation(self, variation_type:str):
        """Specify the type of scale variations

        Implemented variations
         - ``'3-point'``: 3-point variation around central scales
         - ``'7-point'``: 7-point variation around central scales

        More individual type of variations can be specified via
        :py:func:`Interface.set_custom_variation()`.

        Parameters
        ----------
        variation_type: str
            String corresponding to a defined variation.
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if variation_type == '3-point':
            self.variation_info.append({'type':'scale',
                                        'nvar':3,
                                        'error_method':'envelope',
                                        'custom_list':None})
        elif variation_type == '7-point':
            self.variation_info.append({'type':'scale',
                                        'nvar':7,
                                        'error_method':'envelope',
                                        'custom_list':None})
        else:
            print('Requested variation type \"'+variation_type+'\" is not implemented')
        self.store()


    def pdf_variation(self,method='smpdf'):
        """Include PDF member variation

        There are two different methods of PDF variation. Standard 'full'
        variation and the more efficient 'smpdf' variation. If not specified
        explicitly the client tries to use the more efficient 'smpdf' variation,
        depending on the availability of a corresponding reduced PDF set.
        If 'smpdf' is not available, the 'full' variation is performed.

        Parameters
        ----------
        method: str, default 'smpdf'
            The method of PDF variation.
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if method == 'smpdf' or method == 'full':
            self.variation_info.append({'type':'pdf - '+method,
                                        'nvar':None,
                                        'error_method':None,
                                        'custom_list':None})
        else:
            print('Requested PDF variation method \"'+method+'\" is not implemented')

        self.store()


    def set_custom_variation(self, variations:list,method:str):
        """Define custom variations.

        Parameters
        ----------
        variations: list(str)
            Each string has to be of format "muR,muF,pdf,pdf_member".
        method: str
            The method to compute the error from the variation
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self.variation_info.append({'type':'custom',
                                    'nvar':len(variations),
                                    'error_method':method,
                                    'custom_list':variations})
        self.store()


    def cuts(self, cuts):
        """Specify phase space cuts.
        This allows to contrain the phase space of the
        requested process. For processes which required generation cuts, the user
        cuts have to be more exclusive then the generation cuts. If there are not
        the result will be correct for combined cuts, generation and user cuts,
        only (which may render the user cuts irrelevant). With other words the
        generation cuts are **always** applied on top of the user cuts.

        Parameters
        ----------
        cuts: list(str)
            Each string has to be unequality equation of defined variables.
        """

        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if type(cuts) == str:
            if self._is_valid_cut(cuts):
                if 'cuts' in self.requests[0]['json']:
                    self.requests[0]['json']['cuts'].append(cuts)
                else:
                    self.requests[0]['json']['cuts'] = [cuts]
            else:
                print("WARNING: "+cuts+" is not a valid cut, will be ignored.")
        elif type(cuts) == list:
            for cut in cuts:
                if self._is_valid_cut(cut):
                    if 'cuts' in self.requests[0]['json']:
                        self.requests[0]['json']['cuts'].append(cut)
                    else:
                        self.requests[0]['json']['cuts'] = [cut]
                else:
                    print("WARNING: "+cut+" is not a valid cut, will be ignored.")
        else:
            print("WARNING: "+cut+" is not a valid cut, will be ignored.")
        self.store()

    ###########################################################################
    # file operations                                                         #
    ###########################################################################

    def store(self):
        """Store job information on drive
        """
        newdict = {
            'proc':self.proc,
            'valid_contributions':self.valid_contributions,
            'custom_variables':self.custom_variables,
            'variation_info':self.variation_info,
            'variations':self.variations,
            'requests':self.requests,
            'status':self.status
            }

        with open(self.filename,'w') as fp:
            json.dump(newdict,fp,indent=2)

    def read_json(self,filename:str):
        """Read in request specification from json file

        Parameters
        ----------
        filename: str
            Path specification for JSON file.
        """
        if self.status == 'submitted' or self.status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        with open(filename,'r') as fp:
            self.requests[0]['json'] = json.load(fp)


    def write_json(self,filename:str):
        """Write histogram to specified file in json format

        Parameters
        ----------
        filename: str
            Path specification for JSON file.
        """
        with open(filename,'w') as fp:
            json.dump(self.requests[0]['json'],fp,indent=2)
