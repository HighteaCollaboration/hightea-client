import json
import time
from pathlib import Path
from datetime import datetime
import os
import numpy as np
import copy

from .apiactions import API, FIBO, saturate, DEFAULT_ENDPOINT
from .datahandler import DataHandler

class Interface:
    """High-level user interface to the HighTEA database

    Examples
    --------
    >>> job = hightea('jobname')
    >>> job.process('pp_ttx_13TeV')
    >>> job.contribution('LO')
    >>> job.observable('pt_t',[0.,50.,100.,150.,200.,250.])
    >>> job.request()
    >>> job.show_result()
    """

    def __init__(self,
                 name:str,
                 directory='.',
                 overwrite=False,
                 *,
                 auth=None,
                 endpoint=DEFAULT_ENDPOINT):
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

        auth: str
            Authentication token. If not present use anonymous login.
            (optional)

        endpoint: str
            Request endpoint. Debugging tool. (optional)

        """
        if auth:
            self._api = API(auth=auth,endpoint=endpoint)
        else:
            self._api = API(endpoint=endpoint)
            self._api.anonymous_login()

        self._name = name
        self._directory = directory
        # create directory in case it doesn't exist
        Path(directory).mkdir(parents=True, exist_ok=True)
        Path(directory+'/hightea-jobs/').mkdir(parents=True, exist_ok=True)
        self._filename = directory+'/hightea-jobs/'+name+'.job'

        if Path(self._filename).is_file() and not overwrite:
            print("Load data from :",self._filename)
            jsonfile = {}
            with open(self._filename,'r') as fp:
                jsonfile = json.load(fp)

            self._proc                = jsonfile['proc']
            self._metadata            = jsonfile['metadata']
            self._valid_contributions = jsonfile['valid_contributions']
            self._contributions       = jsonfile['contributions']
            self._custom_variables    = jsonfile['custom_variables']
            self._muR                 = jsonfile['muR']
            self._muF                 = jsonfile['muF']
            self._pdf                 = jsonfile['pdf']
            self._pdf_member          = jsonfile['pdf_member']
            self._variation_info      = jsonfile['variation_info']
            self._variations          = jsonfile['variations']
            self._cuts                = jsonfile['cuts']
            self._jet_parameters      = jsonfile['jet_parameters']
            self._observables         = jsonfile['observables']
            self._requests            = jsonfile['requests']
            self._result              = jsonfile['result']
            self._status              = jsonfile['status']
        else:
            if overwrite and Path(self._filename).is_file():
                print("Remove data from :",self._filename)
                os.remove(self._filename)

            self._proc                = ''
            self._metadata            = {}
            self._valid_contributions = []
            self._contributions       = []
            self._custom_variables    = {}
            self._muR                 = None
            self._muF                 = None
            self._pdf                 = None
            self._pdf_member          = 0
            self._variation_info      = []
            self._variations          = []
            self._cuts                = []
            self._jet_parameters      = None
            self._observables         = []
            self._requests            = []
            self._result              = None
            self._status              = 'preparation'
            self.store()


    ###########################################################################
    # internal member functions                                               #
    ###########################################################################

    def _print_metadata(self, proc, metadata):
        """Nicely formatted metadata printout

        Parameters
        ----------
        proc: str
            Process tag

        metadata: dict
            A dictionary containing the metadata as returned by the HighTEA
            API.
        """
        print('  ',metadata['name'],'\n')
        print('Process tag         : ',proc.replace('processes/',''),
              ' (use for process specification)')
        layout = metadata.get('layout')
        if layout:
            print('Momenta layout      :  ', end='')
            particles = []
            jetID = 1
            for entry in layout:
                if isinstance(entry, dict):
                    particles.append(list(entry.values())[0])
                elif ('jet_parton_momenta' in entry):
                    particles.append(f' j{jetID}')
                    jetID += 1
            print(particles)
        print('Default scales      : ',metadata['scales_info'])
        print('Default pdf         : ',metadata['pdf_set'],'/',
              metadata['pdf_member'])
        print('Avail. contributions: ',
              list(metadata.get('contribution_groups',{}).keys()))
        print('Predefined variables')
        for var in metadata['variables'].keys():
            print('  ','{0: <10}'.format(var),' : ',metadata['variables'][var])
        jet_parameters = metadata.get('default_jet_parameters',{})
        if len(jet_parameters):
            print('Jet parameters      :', end='')
            for entry in jet_parameters:
                print(' ',entry,' : ',jet_parameters[entry])
        print(metadata["details"])


    def _finalize_request(self):
        """Checks and finalize a request before submitting
        """
        self._compile_variations()


    def _compile_variations(self):
        """Compile variations if requested.

        Checks if a variation is requested and if yes compiles a
        list of individual scale/pdf choices to be computed.
        """

        if len(self._variation_info) == 0:
            basic_request = {
                'json':{
                    'contributions'    : self._contributions,
                    'custom_variables' : self._custom_variables,
                    'muR'              : self._muR,
                    'muF'              : self._muF,
                    'pdf'              : self._pdf,
                    'pdf_member'       : self._pdf_member,
                    'cuts'             : self._cuts,
                    'jet_parameters'   : self._jet_parameters,
                    'observables'      : self._observables,
                    },
                'token':None,'status':None,'result':None
                }
            self._requests.append(basic_request.copy())
            self.store()
            return;

        # default values
        mur = self._metadata['muR0']
        muf = self._metadata['muF0']
        pdf = self._metadata['pdf_set']
        pdf_member = self._metadata['pdf_member']

        # overwrite with user input
        if self._muR: mur = self._muR
        if self._muF: muf = self._muF
        if self._pdf: pdf = self._pdf
        if self._pdf_member: pdf_member = self._pdf_member

        # build up the list of setups
        list_of_setups = [mur+','+muf+','+pdf+','+str(pdf_member)]
        for var in self._variation_info:
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
                    # this name is constructed by convention
                    pdf_smpdf = cur_pdf+'_'+self._proc.replace('processes/','')+'_smpdf'
                    if pdf_smpdf in self._metadata['available_pdfs']:
                        cur_pdf = pdf_smpdf

                if self._metadata['available_pdfs'][cur_pdf]['error_method'] == 'none':
                    print('No PDF variation available for PDF set: '+cur_pdf)
                else:
                    nmembers = self._metadata['available_pdfs'][cur_pdf]['nmembers']
                    var['nvar'] = nmembers
                    var['error_method'] = self._metadata['available_pdfs'][cur_pdf]['error_method']
                    for it in range(1,nmembers):
                        list_of_setups.append(mur+','+muf+','+cur_pdf+','+str(it))

            if var['type'] == 'custom':
                for setup in var['custom_list']:
                    list_of_setups.append(setup)

        # store list of setups for convenience
        self._variations = list_of_setups

        # create requests
        for setup in list_of_setups:
            muRval, muFval, pdfval, pdfmval = setup.split(',')

            req = {
                'json':{
                    'contributions'    : self._contributions,
                    'custom_variables' : self._custom_variables,
                    'muR'              : muRval,
                    'muF'              : muFval,
                    'pdf'              : pdfval,
                    'pdf_member'       : pdfmval,
                    'cuts'             : self._cuts,
                    'jet_parameters'   : self._jet_parameters,
                    'observables'      : self._observables,
                    },
                'token':None,'status':None,'result':None
                }

            self._requests.append(req)

        self.store()


    def _finalize_result(self):
        """Finalized the results, i.e. computes systematic uncertainties.
        """
        # The first entry is by construction the central prediction
        final_result = copy.deepcopy(self._requests[0]['result'])

        count = 1;
        # do one variation at a time
        for var_info in self._variation_info:
            comb = DataHandler(final_result);
            # this relies on the order of setups in compile_variations
            for reqit in range(1,var_info['nvar']):
                comb.add_data(self._requests[count]['result'])
                count += 1
            # the DataHandler class modifies the first results by adding
            # the computed sys_errors
            rescale_factor = var_info.get('rescale_factor',1.)
            comb.compute_uncertainty(var_info['error_method'],rescale_factor)
            final_result = comb.get_result()

        final_result['info']['name'] = self._name
        self._result = final_result

        self.store()


    ###########################################################################
    # internal checks                                                         #
    ###########################################################################

    def _is_valid_contribution(self, con):
        """Return true if con is a correct contribution.

        Parameters
        ----------
        con: str
            A string specifying a contribution
        """
        if con in self._valid_contributions:
            return True
        else:
            return False


    def _is_valid_obs_spec(self, obs_spec):
        """Return true if bin is correct observable specification.

        Parameters
        ----------
        obs_spec: dict
            A dictionary specifying an observable (dict containing a valid
            'binning' member).
        """
        if type(obs_spec) == dict and 'binning' in obs_spec:
            success = True
            for e in obs_spec['binning']:
                if self._is_valid_bin_spec(e) == False:
                    success = False
            return success
        else:
            return False


    def _is_valid_bin_spec(self, bin_spec):
        """Return true if bin is correct 1D bin specification.

        Parameters
        ----------
        bin_spec:
            A dictionary containing a 'variable' and 'bins' member.
        """
        if type(bin_spec) == dict and 'variable' in bin_spec and 'bins' in bin_spec:
            for it in range(0,len(bin_spec['bins'])-1):
                if bin_spec['bins'][it] >= bin_spec['bins'][it+1]: return False
            return True
        else:
            return False


    def _is_valid_process(self, proc):
        """Return true if proc is in a valid format

        Parameters
        ----------
        proc: str
            A string specifying a process.
        """
        if type(proc) == str:
            return True
        else:
            return False


    def _is_valid_cut(self, cut):
        """Return true if cut is a valid cut

        Parameters
        ----------
        cut: str
            A string specifying a cut
        """
        if type(cut) == str:
            return True;
        else:
            return False;


    def _is_valid_jet_parameters(self, jet_parameters):
        """Return true if jet_parameters is a valid jet_parameters spec

        Parameters
        ----------
        jet_parameters: dict
            A dict containing "maxnjet", "p" and "R".
        """
        if type(jet_parameters) == dict:
            success = True
            if 'maxnjet' not in jet_parameters: success = False
            if 'p' not in jet_parameters: success = False
            if 'R' not in jet_parameters: success = False
            return success;
        else:
            return False;


    ###########################################################################
    # simple database interactions                                            #
    ###########################################################################

    def list_processes(self, detailed=True):
        """Request the list of available processes from the server.

        Parameters
        ----------
        detailed: bool, default True
            If `True` detailed information for each process is provided, if
            `False` only the process key is shown.
        """

        processes = self._api.list_processes()
        for proc in processes:
            if proc != 'processes/tests':
                if detailed:
                    print('#############################################\n')
                    metadata = self._api.simple_req('get',proc)
                    self._print_metadata(proc,metadata)
                    print('\n')
                else:
                    print(proc.replace('processes/',''))


    def list_pdfs(self):
        """Request the list of available pdfs from the server.
        """
        pdfs = self._api.list_pdfs()
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

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if self._is_valid_process(proc):
            self._proc = 'processes/'+proc
            self._metadata = self._api.simple_req('get',self._proc)
            if verbose: self._print_metadata(self._proc,self._metadata)
            self._valid_contributions = list(self._metadata.get('contribution_groups',{}).keys())

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
        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self._custom_variables[name] = definition

        self.store()


    def add_variable_definitions(self, definitions:dict):
        """Add variable definitions from dictionary.

        The specified to be a dictionary of ``"name":"definition"`` pairs.

        Parameters
        ----------
        definitions: dict
            The dictionary containing the definitions.
        """
        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        for key in definitions.keys():
            if not type(definitions[key]) == str:
                print('WARNING: Definition not a string. Not added.')
            else:
                self._custom_variables[key] = definitions[key]

        self.store()


    def store_variable_definitions(self, filename:str):
        """Store variable definitions to file.

        Parameters
        ----------
        filename: str
            The filename containing the definitions.
        """

        with open(filename,'w') as fp:
            json.dump(self._custom_variables,fp,indent=2)


    def load_variable_definitions(self, filename:str):
        """Load variable definitions from file.

        The specified file is expected to be json dictionary of
        ``"name":"definition"`` pairs.

        Parameters
        ----------
        filename: str
            The filename containing the definitions.
        """
        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        with open(filename,'r') as fp:
            new_variables = json.load(fp)
            for key in new_variables.keys():
                if not type(new_variables[key]) == str:
                    print('WARNING: Definition not a string. Not added.')
                else:
                    self._custom_variables[key] = new_variables[key]

        self.store()


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

        if len(self._requests) > 0:
            print('WARNING: job already submitted. Nothing submitted.')
            return

        self._finalize_request()

        if len(self._requests) == 0:
            print('WARNING: job does not contain requests. Nothing submitted.')
            return

        ids = list(range(0,len(self._requests)))

        # submit all requests
        for it in ids:
            resp = self._api.simple_req('post',
                                        self._proc+'/hist',
                                        data=self._requests[it]['json'])
            self._requests[it]['token'] = resp['token']
            self._requests[it]['status'] = 'submitted'

        self._status = 'submitted'
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

        if self._status == 'finished': return True

        ids = list(range(0,len(self._requests)))

        finished = True
        for jt, req in enumerate(self._requests):
            if req['status'] == 'submitted':
                resp = self._api.simple_req('get',f'token/'+req['token'])
                if resp['status'] == 'completed':
                    self._requests[jt]['result'] = json.loads(resp['result'])
                    self._requests[jt]['status'] = 'completed'
                elif resp == 'errored':
                    print('error occured    : ',datetime.now())
                    self._requests[it]['status'] = 'errored'
                else:
                    finished = False;

        self.store()
        if finished:
            self._finalize_result()
            self._status = 'finished'
            self.store()

        return finished


    def get_requests(self):
        """Return the stored requests
        This includes not only the request but also the results in raw format

        Notes
        -----
        This routine is meant for debugging and troubleshooting.
        """

        return self._requests


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

        if self._status != 'finished':
            print('WARNING: job not finished, no results available')
            return

        return self._result


    def raw_result(self):
        """Return the raw results of a job.

        The returned dictionary can be used within the hightea-plotting
        routines.

        Returns
        -------
        results: list(dict)
            A list of dictionaries containing the results.
        """

        if self._status != 'finished':
            print('WARNING: job not finished, no results available')
            return

        return [ req['result'] for req in self._requests ]


    def show_result(self):
        """Print the result in a human readable form
        """

        res = self.result()
        info = self._requests[0]['json']

        f_bin = "{0:9.5g}"
        f_xsec = "{0:11.5g}"
        f_var  = "{0:9.2g}"

        print('Name                    : ',self._name)
        print('Contributions           : ',self._contributions)
        if self._muR: print('muR                     : ',self._muR)
        if self._muF: print('muF                     : ',self._muF)
        if self._pdf: print('pdf                     : ',self._pdf,',',self._pdf_member)

        print('fiducial xsection       : ',f_xsec.format(res['fiducial_mean']))
        print('fiducial xsection error : ',f_xsec.format(res['fiducial_error']))

        for it, var_info in enumerate(self._variation_info):
            print('systematic unc. [%]     : '+var_info['type']+' ('+str(var_info['nvar'])+')')
            var_ce = res['fiducial_mean']
            var_up = res['fiducial_sys_error'][it]['pos']
            var_do = res['fiducial_sys_error'][it]['neg']
            print('                        : '+\
                  ' +'+f_var.format((var_up)/var_ce*100.)+\
                  '/ -'+f_var.format((var_do)/var_ce*100.))

        # compute and print histograms
        for it, histo in enumerate(res['histograms']):

            # observable information
            binning_info = self._observables[it]['binning']
            dimension = len(binning_info)
            # compile binning name
            variable_str = self._observables[it].get('name','')
            if variable_str == '':
                for jt in range(0,dimension):
                    if jt == 0:
                        variable_str += binning_info[jt]['variable']
                    else:
                        variable_str += ' x '+binning_info[jt]['variable']

            print('Histogram     :',variable_str)
            header = ''
            for jt in range(0,dimension):
                header += ' bin'+str(jt+1)+' low  |'
                header += ' bin'+str(jt+1)+' high |'
            header += ' sigma [pb]  | mc-err [pb] |'
            for jt, var_info in enumerate(self._variation_info):
                header += (' '+var_info['type']+' ('+str(var_info['nvar'])+')'+' [%] |').rjust(24)

            print(header)
            length = len(histo['binning'])
            for binit in range(0,length):
                line = ''
                # bins
                for it in range(0,dimension):
                    line += ' '+f_bin.format(histo['binning'][binit]['edges'][it]['min_value'])+' |'
                    line += ' '+f_bin.format(histo['binning'][binit]['edges'][it]['max_value'])+' |'

                line += ' '+f_xsec.format(histo['binning'][binit]['mean'])+' |'
                line += ' '+f_xsec.format(histo['binning'][binit]['error'])+' |'
                for jt, var_info in enumerate(self._variation_info):
                    var_ce = histo['binning'][binit]['mean']
                    var_up = histo['binning'][binit]['sys_error'][jt]['pos']
                    var_do = histo['binning'][binit]['sys_error'][jt]['neg']
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

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        success = True
        if type(con) == list:
            for e in con:
                if self._is_valid_contribution(e) == False:
                    success = False
            if success:
                self._contributions = con
        elif type(con) == str and self._is_valid_contribution(con):
            self._contributions = [con]
        else:
            success = False

        if success == False:
            print('WARNING: contributions(con)')
            print(' -> con has to be a single string or a list of strings.')
            print(' -> Nothing has been changed.')

        self.store()


    def observable(self, observable):
        """Define the binning for observables via dictionaries.

        Each dict is check to have at least the "binning" key words.

        Parameters
        ----------
        binning: dict or list(dict)
            A dict (or list of dicts) defining the observables(s)
        """

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        success = True
        if type(observable) == list:
            for e in binning:
                if self._is_valid_obs_spec(e) == False:
                    success = False
            if success:
                for e in binning:
                  self._observables.append(e)
        elif self._is_valid_obs_spec(observable):
            self._observables.append(observable)
        else:
            success = False

        if success == False:
            print('WARNING: observable(observable)')
            print(' -> binning has to be a single (or list of) observable specification.')

        self.store()


    def observable(self, variable:str, binning:list, name=None):
        """Add a observable defined by a variable and bin specification

        Parameters
        ----------
        variable: str
            The variable to be binned.
        binning: list(float)
            A list of bin edges.
        name: str
            A label for the observable (optional)
        """

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        new_obs_spec = {'binning':[{'variable':variable,'bins':binning}]}
        if name and type(name) == str : new_obs_spec['name'] = name

        if self._is_valid_obs_spec(new_obs_spec):
            self._observables.append(new_obs_spec)

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

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self._muR = muR
        self._muF = muF

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

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self._pdf = pdf
        self._pdf_member = pdf_member

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

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if variation_type == '3-point':
            self._variation_info.append({'type':'scale',
                                         'nvar':3,
                                         'error_method':'envelope',
                                         'custom_list':None})
        elif variation_type == '7-point':
            self._variation_info.append({'type':'scale',
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

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if method == 'smpdf' or method == 'full':
            self._variation_info.append({'type':'pdf - '+method,
                                         'nvar':None,
                                         'error_method':None,
                                         'custom_list':None})
        else:
            print('Requested PDF variation method \"'+method+'\" is not implemented')

        self.store()


    def set_custom_variation(self, variations:list, method:str):
        """Define custom variations.

        Parameters
        ----------
        variations: list(str)
            Each string has to be of format "muR,muF,pdf,pdf_member".
        method: str
            The method to compute the error from the variation
        """

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        self._variation_info.append({'type':'custom',
                                     'nvar':len(variations),
                                     'error_method':method,
                                     'custom_list':variations})

        self.store()


    def cuts(self, cuts):
        """Specify phase space cuts.

        This allows to constrain the phase space for the requested process.
        For processes which required generation cuts, the user cuts have to be
        more exclusive then the generation cuts. If they are not the result will
        correspond to the union of generation and user cuts only (which may
        render the user cuts irrelevant). With other words the generation cuts
        are **always** applied on top of the user cuts.

        Parameters
        ----------
        cuts: list(str)
            Each string has to be inequality equation of defined variables.
        """

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if type(cuts) == str:
            if self._is_valid_cut(cuts):
                self._cuts.append(cuts)
            else:
                print("WARNING: "+cuts+" is not a valid cut, will be ignored.")
        elif type(cuts) == list:
            for cut in cuts:
                if self._is_valid_cut(cut):
                    self._cuts.append(cut)
                else:
                    print("WARNING: "+cut+" is not a valid cut, will be ignored.")
        else:
            print("WARNING: "+cuts+" is not a valid cut, will be ignored.")

        self.store()


    def jet_parameters(self, jet_parameters):
        """Specify jet parameters.

        This allows to specify parameters for the jet algorithm. This is
        possible for processes where a corresponding default parameters set
        is defined in the metadata.

        The following parameter are available:
         - ``'nmaxjet'``: the number of jets returned by the algorithm
         - ``'p'``      : the power of the kt-algorithm (-1: anti-kT,1: kt)
         - ``'R'``      : the radius parameter

        **NOTE**: Please be advised that, similar to cuts, results for processes
        that require a jet-algorithm on the generation level are only correct
        for more exclusive definitions of the jet-algorithm. This is a bit more
        subtle in case of the jet-algorithm case and therefore these parameters
        should be used carefully.

        Parameters
        ----------
        jet_parameters: dict
            A dict containing the members 'nmaxjet'(int), 'p'(int), 'R'(float).
        """

        if self._status == 'submitted' or self._status == 'finished':
            print('WARNING: job already submitted. Nothing changed')
            return

        if self._is_valid_jet_parameters(jet_parameters) and 'default_jet_parameters' in self._metadata :
            self._jet_parameters = jet_parameters
        else:
            print("WARNING: jet_parameters is not valid, will be ignored.")

        self.store()


    ###########################################################################
    # file operations                                                         #
    ###########################################################################

    def store(self):
        """Store job information on drive
        """

        newdict = {
            'proc'                : self._proc,
            'metadata'            : self._metadata,
            'valid_contributions' : self._valid_contributions,
            'contributions'       : self._contributions,
            'custom_variables'    : self._custom_variables,
            'muR'                 : self._muR,
            'muF'                 : self._muF,
            'pdf'                 : self._pdf,
            'pdf_member'          : self._pdf_member,
            'variation_info'      : self._variation_info,
            'variations'          : self._variations,
            'cuts'                : self._cuts,
            'jet_parameters'      : self._jet_parameters,
            'observables'         : self._observables,
            'requests'            : self._requests,
            'result'              : self._result,
            'status'              : self._status
            }

        with open(self._filename,'w') as fp: json.dump(newdict,fp,indent=2)
