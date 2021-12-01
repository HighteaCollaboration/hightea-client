import json
import time
from pathlib import Path
from datetime import datetime
import os
import numpy as np

from .apiactions import API,FIBO,saturate

class Interface:
    """High-level user interface to the HighTEA database

    Examples
    --------
    >>> job = hightea('jobname')
    >>> job.process('pp_ttx_13TeV')
    >>> job.add_histogram()
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
            jsonfile = {}
            with open(self.filename,'r') as fp:
                jsonfile = json.load(fp)
            self.proc = jsonfile['proc']
            self.valid_contributions = jsonfile['valid_contributions']
            self.custom_variables = jsonfile['custom_variables']
            self.histograms = jsonfile['histograms']
            self.metadata = self.api.simple_req('get',self.proc)
        else:
            if overwrite and Path(self.filename).is_file():
                os.remove(self.filename)
            self.proc = ''
            self.metadata = {}
            self.valid_contributions = []
            self.custom_variables = {}
            self.histograms = []
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


    def _finalize_request(self,hid):
        """Checks and finalize a request before submitting
        """
        self._compile_variations(hid)
        self.histograms[hid]['json']['custom_variables'] = self.custom_variables


    def _compile_variations(self,hid):
        """Compile variations if requested
        Checks if histogram hid has a variation request and if yes
        compiles the list of required scale/pdf choices
        """
        if not 'variation' in self.histograms[hid]:
            return True;

        mur = 'muR0'
        muf = 'muF0'
        pdf = self.metadata['pdf_set']
        pdf_member = self.metadata['pdf_member']
        if 'muR' in self.histograms[hid]['json']:
            mur = self.histograms[hid]['json']['muR']
        if 'muF' in self.histograms[hid]['json']:
            muf = self.histograms[hid]['json']['muF']
        if 'pdf' in self.histograms[hid]['json']:
            pdf = self.histograms[hid]['json']['pdf']
        if 'pdf_member' in self.histograms[hid]['json']:
            pdf_member = self.histograms[hid]['json']['pdf_member']

        list_of_setups = [mur+','+muf+','+pdf+','+str(pdf_member)]
        for var in self.histograms[hid]['variation']:
            if var == '3-point':
                list_of_setups.append(mur+'*2,'+muf+'*2,'+pdf+','+str(pdf_member))
                list_of_setups.append(mur+'/2,'+muf+'/2,'+pdf+','+str(pdf_member))
            if var == '7-point':
                list_of_setups.append(mur+'*2,'+muf+'*2,'+pdf+','+str(pdf_member))
                list_of_setups.append(mur+'/2,'+muf+'/2,'+pdf+','+str(pdf_member))
                list_of_setups.append(mur+','+muf+'*2,'+pdf+','+str(pdf_member))
                list_of_setups.append(mur+','+muf+'/2,'+pdf+','+str(pdf_member))
                list_of_setups.append(mur+'*2,'+muf+','+pdf+','+str(pdf_member))
                list_of_setups.append(mur+'/2,'+muf+','+pdf+','+str(pdf_member))
            if var == 'pdf':
                
                if self.metadata['available_pdfs'][pdf]['error_method'] == 'none':
                    print('No PDF variation available for PDF set: '+pdf)
                else:
                    nmembers = self.metadata['available_pdfs'][pdf]['nmembers']
                    for it in range(0,nmembers):
                        list_of_setups.append(mur+','+muf+','+pdf+','+str(it))
            if type(var) == list:
                for setup in var:
                    list_of_setups.append(setup)

        self.histograms[hid]['variations'] = list_of_setups
        return True;


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
        with open(filename,'r') as fp:
            new_variables = json.load(fp)
            for key in new_variables.keys():
                if not type(new_variables[key]) == str:
                    print('WARNING: Definition not a string. Not added.')
                else:
                    self.custom_variables[key] = new_variables[key]


    def store_variable_definitions(self, filename:str):
        """Store variable definitions to file.

        Parameters
        ----------
        filename: str
            The filename containing the definitions.
        """
        with open(filename,'w') as fp:
            json.dump(self.custom_variables,fp,indent=2)


    def add_histogram(self, js=None):
        """Add histogram to the job
        The routine will return the histogram identification number which can
        be used to modify the histogram later on.

        Parameters
        ----------
        js: str or dict, default None
            If this parameter is a `str` then it will interpret this as a
            file path to a JSON file defining a histogram, i.e. it will load
            the file and adds to the list of histograms. If it is a `dict`
            it directly adds a histogram equal to that dictionary and if `None`
            (default) a empty histogram is added.

        Returns
        -------
        histogram_id: int
            A number identifing the histogram.
        """
        if len(self.histograms) > 0:
            if 'requests' in self.histograms[-1]:
                print('WARNING: job already submitted. Nothing changed')
                return

        new_id = len(self.histograms)
        if js == None:
            self.histograms.append({'json':{'name':'request '+str(new_id)}})
        elif type(js) == dict:
            self.histograms.append({'json':js})
        elif type(js) == str:
            with open(js,'r') as fp:
                self.histograms.append({'json':json.load(fp)})
        else:
            print('WARNING: add_histogram(json=None)')
            print(' -> Input not reconised, either input is a filepath or dict.')
            print(' -> Nothing changed.')
            return -1;

        if 'name' in self.histograms[new_id]['json']:
            self.store()
            return new_id
        else:
           self.histograms[new_id]['json']['name'] = 'request '+str(new_id)
           self.store()
           return new_id


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

        if len(self.histograms) > 0:
            if 'requests' in self.histograms[-1]:
                print('WARNING: job already submitted. Nothing submitted.')
                return
        else:
            print('WARNING: job does not contain histogram. Nothing submitted.')
            return

        ids = list(range(0,len(self.histograms)))

        # Finalize requests -> compile variations.
        for it in ids: self._finalize_request(it)

        # submit all processes
        for it in ids:
            self.histograms[it]['requests'] = []
            if 'variations' in self.histograms[it]:
                 for setup in self.histograms[it]['variations']:
                     js = self.histograms[it]['json'].copy()
                     muRval, muFval, pdfval, pdfmval = setup.split(',')
                     js['muR'] = muRval
                     js['muF'] = muFval
                     js['pdf'] = pdfval
                     js['pdf_member'] = pdfmval

                     resp = self.api.simple_req('post',
                                                self.proc+'/hist',
                                                data=js)
                     self.histograms[it]['requests'].append(
                       [resp['token'],'submitted']
                     )
            else:
                js = self.histograms[it]['json'].copy()
                resp = self.api.simple_req('post',
                                           self.proc+'/hist',
                                           data=js)
                self.histograms[it]['requests'].append(
                       [resp['token'],'submitted']
                     )

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

        ids = list(range(0,len(self.histograms)))

        finished = True
        for it in ids:
            for jt, req in enumerate(self.histograms[it]['requests']):
                if req[1] == 'submitted':
                    resp = self.api.simple_req('get',f'token/'+req[0])
                    if resp['status'] == 'completed':
                        self.histograms[it]['requests'][jt][1] =  json.loads(resp['result'])
                    elif resp == 'errored':
                        print('error occured    : ',datetime.now())
                        self.histograms[it]['requests'][jt][1] = 'error'
                    else:
                        finished = False;

        self.store()
        return finished


    def get_histograms(self):
        """Return the stored histograms
        This includes not only the request but also the results in raw format

        Notes
        -----
        This routine is meant for debugging and troubleshooting.
        """
        return self.histograms.copy()


    def result(self):
        """Return the results of a request
        """
        all_output = []
        for hid in range(0,len(self.histograms)):
            if 'requests' in self.histograms[hid]:
                histo_var = []
                fiducial_mean_var = []
                fiducial_error_var = []
                for req in self.histograms[hid]['requests']:
                    histo_var.append(req[1]['histogram'])
                    fiducial_mean_var.append(req[1]['fiducial_mean'])
                    fiducial_error_var.append(req[1]['fiducial_error'])
                info = self.histograms[hid]['json'].copy()
                if 'variations' in self.histograms[hid]:
                    info['variations'] = self.histograms[hid]['variations']

                histo_comb = []
                for binit in range(0,len(histo_var[0])):
                    new_bin = {
                        'edges':histo_var[0][binit]['edges'],
                        'mean':[],'error':[]
                    }
                    for varit in range(0,len(histo_var)):
                        new_bin['mean'].append(histo_var[varit][binit]['mean'])
                        new_bin['error'].append(histo_var[varit][binit]['error'])
                    histo_comb.append(new_bin)

                output = {
                 'histogram':histo_comb,
                 'fiducial_mean':fiducial_mean_var,
                 'fiducial_error':fiducial_error_var,
                 'info':info
                }

                all_output.append(output)
            else:
                print("WARNING: result for histogram "+str(hid)+" not available")
        return all_output


    ###########################################################################
    # histogram interactions                                                  #
    ###########################################################################

    def description(self, name:str, hid=None):
        """Add a description to a histogram.
        This description can be used to easily organize your results.
        It is included automatically during plotting with the hightea-plotting
        library.

        Parameters
        ----------
        name: str
            A descriptive name for the histogram
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1
        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        self.histograms[hid]['json']['name'] = name
        self.store()


    def contribution(self, con, hid=None):
        """Define contribution(s) for histogram.

        Parameters
        ----------
        con: str or list(str)
            A string (or list of strings) defining the contribution(s)
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        success = True
        if type(con) == list:
            for e in con:
                if self._is_valid_contribution(e) == False:
                    success = False
            if success:
                self.histograms[hid]['json']['contributions'] = con
        elif type(con) == str and self._is_valid_contribution(con):
            self.histograms[hid]['json']['contributions'] = [con]
        else:
            success = False

        if success == False:
            print('WARNING: contributions(con,hid)')
            print(' -> con has to be a single string or a list of strings.')
            print(' -> Histogram '+str(hid)+' has not been changed')

        self.store()


    def binning(self, binning, hid=None):
        """Define the binning for histogram via dictionaries.

        Each dict is check to have at least the "variable" and "bins" key words.

        Parameters
        ----------
        binning: dict or list(dict)
            A dict (or list of dicts) defining the binning(s)
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        success = True
        if type(binning) == list:
            for e in binning:
                if self._is_valid_bin_spec(e) == False:
                    success = False
            if success:
                self.histograms[hid]['json']['binning'] = binning
        elif self._is_valid_bin_spec(binning):
            self.histograms[hid]['json']['binning'] = [binning]
        else:
            success = False

        if success == False:
            print('WARNING: binning(binning,hid)')
            print(' -> binning has to be a single bin specification or a list.')
            print(' -> Histogram '+str(hid)+' has not been changed')

        self.store()


    def binning(self, variable:str, binning:list, hid=None):
        """Add a binning in variable (string) with specified bins (list)

        Parameters
        ----------
        variable: str
            The variable to be binned.
        binning: list(float)
            A list of bin edges.
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        new_bin_spec = {'variable':variable,'bins':binning}
        if 'binning' in self.histograms[hid]['json']:
            self.histograms[hid]['json']['binning'].append(new_bin_spec)
        else:
            self.histograms[hid]['json']['binning'] = [new_bin_spec]
        self.store()


    def scales(self, muR:str, muF:str, hid=None):
        """Define the central scale choices
        Define the central choice for the renormalization (muR) and
        factorization (muF) scale

        Parameters
        ----------
        muR: str
            Expression to define muR.
        muF: str
            Expression to define muF.
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        self.histograms[hid]['json']['muR'] = muR
        self.histograms[hid]['json']['muF'] = muF
        self.store()


    def pdf(self, pdf:str, pdf_member=0, hid=None):
        """Define the pdf

        Parameters
        ----------
        pdf: str
            PDF name (refer to :py:func:`Interface.list_pdfs()`).

        pdf_member: int, default 0
            Specify PDF member

        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        self.histograms[hid]['json']['pdf'] = pdf
        self.histograms[hid]['json']['pdf_member'] = pdf_member
        self.store()


    def scale_variation(self, variation_type:str, hid=None):
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
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        if variation_type == '3-point' or variation_type == '7-point':
            if 'variation' in self.histograms[hid]:
                self.histograms[hid]['variation'].append(variation_type)
            else:
                self.histograms[hid]['variation'] = [variation_type]
        else:
            print('Requested variation type \"'+variation_type+'\" is not implemented')
        self.store()


    def pdf_variation(self, hid=None):
        """Specify the type of pdf variation.

        Implemented variations
         - 'standard': Full pdf member variation to determine pdf uncertainties as
                       specified by pdf set. NOTE: This might be time consuming as
                       it corresponds to O(100) reweight setups.
         - 'reduced' : For many available pdf sets a reduced member set has been
                       produced within the SMPDF formalism (CITE). This allows for
                       faster pdf uncertainty estimatation (O(10) reweight setups).
                       This approach typically reproduces 'standard' pdf uncertainty
                       up to O(1%) accuracy.

        Parameters
        ----------
        variation_type: str
            String corresponding to a defined variation.
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        if 'variation' in self.histograms[hid]:
            self.histograms[hid]['variation'].append('pdf')
        else:
            self.histograms[hid]['variation'] = ['pdf']

        self.store()


    def set_custom_variation(self, variations:list, hid=None):
        """Define custom variations.

        Parameters
        ----------
        variations: list(str)
            Each string has to be of format "muR,muF,pdf,pdf_member".
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        if 'variation' in self.histograms[hid]:
            self.histograms[hid]['variation'].append(variations)
        else:
            self.histograms[hid]['variation'] = [variations]
        self.store()


    def cuts(self, cuts, hid=None):
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
        hid: int, default None
            Specification of the histogram to be modified. By default
            the last added histogram is modified.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        if type(cuts) == str:
            if self._is_valid_cut(cuts):
                if 'cuts' in self.histograms[hid]['json']:
                    self.histograms[hid]['json']['cuts'].append(cuts)
                else:
                    self.histograms[hid]['json']['cuts'] = [cuts]
            else:
                print("WARNING: "+cuts+" is not a valid cut, will be ignored.")
        elif type(cuts) == list:
            for cut in cuts:
                if self._is_valid_cut(cut):
                    if 'cuts' in self.histograms[hid]['json']:
                        self.histograms[hid]['json']['cuts'].append(cut)
                    else:
                        self.histograms[hid]['json']['cuts'] = [cut]
                else:
                    print("WARNING: "+cut+" is not a valid cut, will be ignored.")
        else:
            print("WARNING: "+cut+" is not a valid cut, will be ignored.")
        self.store()


    def show_result(self):
        """Print the result in a human readable form
        """
        for hid,res in enumerate(self.result()):
            print('Histogram ',hid)

            f_bin = "{0:9.5g}"
            f_xsec = "{0:11.5g}"
            f_var  = "{0:10.2g}"

            print('Name                    : ',res['info']['name'])
            print('Contributions           : ',res['info']['contributions'])
            if 'muR' in res['info']:
                print('muR                     : ',res['info']['muR'])
            if 'muF' in res['info']:
                print('muF                     : ',res['info']['muF'])
            if 'pdf' in res['info']:
                print('pdf                     : ',res['info']['pdf'])
            if 'variation' in self.histograms[hid]:
                print('variation               : ',self.histograms[hid]['variation'])

            # compute and print fiducial cross section
            print('fiducial xsection       : ',f_xsec.format(res['fiducial_mean'][0]))
            print('fiducial xsection error : ',f_xsec.format(res['fiducial_error'][0]))
            setup_it = 1
            if 'variation' in self.histograms[hid]:
                if '3-point' in self.histograms[hid]['variation']:
                    line = 'scale-unc.(3-point) [%] :'
                    scale_ce = res['fiducial_mean'][0]
                    scale_up = np.amax(res['fiducial_mean'][setup_it:setup_it+2])
                    scale_do = np.amin(res['fiducial_mean'][setup_it:setup_it+2])
                    line += ' +'+f_var.format((scale_up-scale_ce)/scale_ce*100.)+\
                           '/ -'+f_var.format((scale_ce-scale_do)/scale_ce*100.)
                    print(line)
                    setup_it += 2
                if '7-point' in self.histograms[hid]['variation']:
                    line = 'scale-unc.(7-point) [%] :'
                    scale_ce = res['fiducial_mean'][0]
                    scale_up = np.amax(res['fiducial_mean'][setup_it:setup_it+6])
                    scale_do = np.amin(res['fiducial_mean'][setup_it:setup_it+6])
                    line += ' +'+f_var.format((scale_up-scale_ce)/scale_ce*100.)+\
                           '/ -'+f_var.format((scale_ce-scale_do)/scale_ce*100.)
                    print(line)
                    setup_it += 6
                if 'pdf' in self.histograms[hid]['variation']:
                    error_method = self.metadata['available_pdfs'][res['info']['pdf']]['error_method']
                    nmembers = self.metadata['available_pdfs'][res['info']['pdf']]['nmembers']
                    line = 'pdf-unc. ('+error_method+') [%] :'
                    pdf_vals = res['fiducial_mean'][setup_it:setup_it+nmembers]
                    pdf_ce = pdf_vals[0]
                    pdf_up = pdf_ce
                    pdf_do = pdf_ce
                    if error_method == 'replicas':
                        pdf_err = np.std(pdf_vals)
                        pdf_up += pdf_err
                        pdf_do -= pdf_err
                    if error_method == 'hessian':
                        #following 0901.0002 sec 6.
                        npairs = (nmembers-1)/2
                        sumdiff_up = 0.
                        sumdiff_do = 0.
                        for parit in range(0,npairs):
                            diffp = pdf_vals[1+parit*2]-pdf_ce
                            diffm = pdf_vals[1+parit*2+1]-pdf_ce
                            sumdiff_up += (np.max([0,diffp,diffm]))**2
                            sumdiff_do += (np.max([0,-diffp,-diffm]))**2
                        pdf_up += np.sqrt(sumdiff_up) 
                        pdf_do += np.sqrt(sumdiff_do) 
                    if error_method == 'symmhessian':
                        #following 0901.0002 sec 6.
                        npairs = nmembers-1
                        sumdiff_up = 0.
                        sumdiff_do = 0.
                        for parit in range(0,npairs):
                            diffp = pdf_vals[1+parit]-pdf_ce
                            sumdiff_up += (np.max([0,diffp]))**2
                            sumdiff_do += (np.max([0,-diffp]))**2
                        pdf_up += np.sqrt(sumdiff_up) 
                        pdf_do += np.sqrt(sumdiff_do) 
                    line += ' +'+f_var.format((pdf_up-pdf_ce)/pdf_ce*100.)+\
                           '/ -'+f_var.format((pdf_ce-pdf_do)/pdf_ce*100.)
                    print(line)
                    setup_it += nmembers

            # compute and print histogram
            histo = res['histogram']
            dimension = len(res['info']['binning'])

            variable_str = ''
            for it in range(0,dimension):
                if it == 0:
                    variable_str += res['info']['binning'][it]['variable']
                else:
                    variable_str += ' x '+res['info']['binning'][it]['variable']

            print('Histogram     :',variable_str)
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
                if 'pdf' in self.histograms[hid]['variation']:
                    error_method = self.metadata['available_pdfs'][res['info']['pdf']]['error_method']
                    header += ' pdf-unc.('+error_method+') [%]  |'
            print(header)
            length = len(histo)
            for binit in range(0,length):
                line = ''
                # bins
                for it in range(0,dimension):
                    line += ' '+f_bin.format(histo[binit]['edges'][it]['min_value'])+' |'
                    line += ' '+f_bin.format(histo[binit]['edges'][it]['max_value'])+' |'

                line += ' '+f_xsec.format(histo[binit]['mean'][0])+' |'
                line += ' '+f_xsec.format(histo[binit]['error'][0])+' |'
                setup_it = 1
                if 'variation' in self.histograms[hid]:
                    if '3-point' in self.histograms[hid]['variation']:
                        scale_ce = histo[binit]['mean'][0]
                        scale_up = np.amax(histo[binit]['mean'][setup_it:setup_it+2])
                        scale_do = np.amin(histo[binit]['mean'][setup_it:setup_it+2])
                        line += ' +'+f_var.format((scale_up-scale_ce)/scale_ce*100.)+\
                               '/ -'+f_var.format((scale_ce-scale_do)/scale_ce*100.)+'|'
                        setup_it += 2
                    if '7-point' in self.histograms[hid]['variation']:
                        scale_ce = histo[binit]['mean'][0]
                        scale_up = np.amax(histo[binit]['mean'][setup_it:setup_it+6])
                        scale_do = np.amin(histo[binit]['mean'][setup_it:setup_it+6])
                        line += ' +'+f_var.format((scale_up-scale_ce)/scale_ce*100.)+\
                               '/ -'+f_var.format((scale_ce-scale_do)/scale_ce*100.)+'|'
                        setup_it += 6
                    if 'pdf' in self.histograms[hid]['variation']:
                        error_method = self.metadata['available_pdfs'][res['info']['pdf']]['error_method']
                        nmembers = self.metadata['available_pdfs'][res['info']['pdf']]['nmembers']
                        pdf_vals = np.array(histo[binit]['mean'][setup_it:setup_it+nmembers])
                        pdf_ce = pdf_vals[0]
                        pdf_up = pdf_ce
                        pdf_do = pdf_ce
                        if error_method == 'replicas':
                            pdf_err = np.sqrt(sum((pdf_vals[1:]-pdf_ce)**2)/(nmembers-1))
                            pdf_up += pdf_err
                            pdf_do -= pdf_err
                        if error_method == 'hessian':
                            #following 0901.0002 sec 6.
                            npairs = (nmembers-1)/2
                            sumdiff_up = 0.
                            sumdiff_do = 0.
                            for parit in range(0,npairs):
                                diffp = pdf_vals[1+parit*2]-pdf_ce
                                diffm = pdf_vals[1+parit*2+1]-pdf_ce
                                sumdiff_up += (np.max([0,diffp,diffm]))**2
                                sumdiff_do += (np.max([0,-diffp,-diffm]))**2
                            pdf_up += np.sqrt(sumdiff_up) 
                            pdf_do += np.sqrt(sumdiff_do) 
                        if error_method == 'symmhessian':
                            #following 0901.0002 sec 6.
                            npairs = nmembers-1
                            sumdiff_up = 0.
                            sumdiff_do = 0.
                            for parit in range(0,npairs):
                                diffp = pdf_vals[1+parit]-pdf_ce
                                sumdiff_up += (np.max([0,diffp]))**2
                                sumdiff_do += (np.max([0,-diffp]))**2
                            pdf_up += np.sqrt(sumdiff_up) 
                            pdf_do += np.sqrt(sumdiff_do) 
                        line += ' +'+f_var.format((pdf_up-pdf_ce)/pdf_ce*100.)+\
                               '/ -'+f_var.format((pdf_ce-pdf_do)/pdf_ce*100.)
                        setup_it += nmembers
                print(line)
            print('\n')

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
            'histograms':self.histograms
            }
        
        with open(self.filename,'w') as fp:
            json.dump(newdict,fp,indent=2)

    def read_json(self,filename:str,hid=None):
        """Read in histogram specification from json file

        Parameters
        ----------
        filename: str
            Path specification for JSON file.
        hid: int, default None
            Specification of the histogram to be printed. By default
            the last added histogram is printed.
        """
        if hid == None: hid = -1

        if 'requests' in self.histograms[hid]:
            print('WARNING: job already submitted. Nothing changed')
            return

        with open(filename,'r') as fp:
            self.histograms[hid]['json'] = json.load(fp)


    def write_json(self,filename:str,hid=None):
        """Write histogram to specified file in json format

        Parameters
        ----------
        filename: str
            Path specification for JSON file.
        hid: int, default None
            Specification of the histogram to be printed. By default
            the last added histogram is printed.
        """
        if hid == None: hid = -1

        with open(filename,'w') as fp:
            json.dump(self.histograms[hid]['json'],fp,indent=2)
