Welcome to HighTEA client's documentation
=========================================

User software for interacting with the HighTEA database from the Centre for Precision Studies in Particle Physics. See the central website of HighTEA (High-energy Theory Event Analysis):

http://www.precision.hep.phy.cam.ac.uk/hightea/

and the physics publication:

ARXIV

View this README including the inline documentation of the python library on [ReadTheDocs](https://hightea-client.readthedocs.io/en/latest/).

Installation
============

This package is available on [PyPi](https://pypi.org/project/hightea-client/) via:

```
pip install hightea-client
```

The python library interface can be imported via `import hightea.client`. For a quick start, we recommend new users to have a look at the examples and tutorial that can be found here:

[HighTEA Examples](https://github.com/HighteaCollaboration/hightea-examples).

For details on the functionality please refer to the [ReadTheDocs](https://hightea-client.readthedocs.io/en/latest/) documentation.

The HighTEA API
===============
Through the interface the users makes web requests to the HighTEA database service. A dynamic documentation of the API can be found [here](https://www.hep.phy.cam.ac.uk/hightea/docs).

Here a description of the most user-relevant APIs:

  - ``api/processes``: Returns a key-value map where the keys are the identifiers for the available processes and the value is the short description of the process. The identifying keys are to be used in subsequent API calls to retrieve metadata or perform analysis on the process. For example browsing to `https://www.hep.phy.cam.ac.uk/hightea/api/processes/` yields
    ```json
    {
      "processes/pp_jx_7TeV":"pp -> j + X at 7 TeV",
      "processes/pp_aax_8TeV":"pp -> a a + X at 8 TeV",
      "processes/pp_ttx_13TeV":"pp -> t tbar +X at 13 TeV with mt = 172.5 GeV"
    }
    ```
    This API call takes no parameters.

  - ``api/proceses/<PROCESS NAME>`` Returns a key-value mapping with the metadata for the process with identifier `<PROCESS NAME>`. Details about the metadata provided can be found below.

    This API call takes no parameters.

  - `api/processes/<PROCESS NAME>/hist` Returns an histogram for the given process based on the user input.

    The API call must be made using the POST request method and contain data as a JSON key value pair which conforms to the following schema:
      * `"observables"` (required, list of observable specifications): A list of dictionaries, each containing:
          - `"name"` (optional): A label for the observable.
          - `"binning"` : A list of dictionaries. A one dimensional histogram contains 1 element, a two dimensional 2 elements and so on. Each containing:
            * `"variable"`: Variable in which to bin.
            * `"bins"`: An ordered list of numbers defining the edges of the bins. The literal `Infinity` is allowed (as it is `- Infinity`).

        The resulting histogram will correspond to the outer product of all the bin specifications in the list.

      * `"custom_variables"` (optional, key value mapping): A map of names to expressions in terms of pre-existing variables or particle momenta. The variables defined here become available for usage in bin specifications, scale definitions and cuts. The expression syntax is described in more detail below.

      * `"cuts"` (optional, list of cuts): A list of inequalities between expressions. The histogram will only consider events for which the inequalities are fulfilled. The expression syntax is described in more detail below.

      * `"pdf"` (optional, string): The PDF set to be used to reweigh the events. If given, $\alpha_S$ and the scales will be evaluated to match the new set.

      * `"muR"` (optional, string): An expression corresponding to the renormalization scale used for reweighing.

      * `"muF"` (optional, string): An expression corresponding to the factorization scale used for reweighing.

      * `"contributions"` (list of strings, optional): A subset of the contributions or contributions groups in a process, typically specifying the perturbative order. If specified, only the weights associated to the listed contributions will be taken into account. By default all contributions are evaluated, which corresponds to highest perturbative order.

    An example of a valid request payload is:
    ```json
    {
        "contributions":["NNLO"],
        "custom_variables": {"circle": "sqrt(pt_top**2 + pt_tbar**2)"},
        "cuts": ["y_tbar <  4", "pt_tbar > 10"],
        "pdf": "CT14nnlo",
        "pdf_member":0,
        "muR": "2*HTo4",
        "muF": "2*m_tt",
        "observables": [
           {
             "name":"my2Dobservable",
             "binning": [
               {
                 "variable": "circle",
                 "bins": [0, 20, 40, 60, 80, "Infinity"]
               },
               {
                 "variable": "m_tt",
                 "bins": [350, 450, 550, 650, "Infinity"]
               }
               ]
           }
           ]
    }
    ```

  - `api/available_pdfs` : Returns a list with the available PDFs that can be used for reweighting.

Description of metadata
-----------------------

The returned mapping includes (but it is not restricted to) the following keys:
  - `name` (string): The short description of the process.

  - `details` (string): A more detailed description of the process.

  - `layout` (list): A specification of the particles available for analysis. Currently the  valid specifications for an item in the lists are:
    A key value pair `"particle_momenta": <NAME OF THE PARTICLE>`. This indicates that the momenta of the listed particles are available for analysis. They are available as variables of the form `p_<NAME OF THE PARTICLE>_<u>` where `<u>` is the 4-momentum index, one of {0, 1, 2, 3}. The index 0 corresponds to the energy, the indexes 1 and 2 correspond to the transverse momentum and the index 3 corresponds the longitudinal momentum. All momenta are provided in the laboratory frame. For example
    ```json
    "layout": [
        {"particle_momenta": "t"},
        {"particle_momenta": "tbar"},
    ]
    ```
    in the top pair production process means that the variable `p_t_0` is the energy of the top quark and `p_tbar_3` is the longitudinal momentum of the anti-top quark.

    In case of final state jets the layout provides the parton momenta which are clustered with a jet algorithm (either the default as specified below or according to the request). The jet are ordered with respect to their transverse momentum and can be accessed by `p_j1_0` etc.

  - `variables` (map of string to string): A mapping of variable names to expressions, corresponding to the default predefined variables available in the analysis. For example
     ```json

     "variables": {
         "pt_t": "sqrt(p_t_1**2 + p_t_2**2)",
         "pt_tbar": "sqrt(p_tbar_1**2 + p_tbar_2**2)",
         "y_t": "0.5*log((p_t_0 + p_t_3)/(p_t_0 - p_t_3))",
         "y_tbar": "0.5*log((p_tbar_0 + p_tbar_3)/(p_tbar_0 - p_tbar_3))"
       }
     ```
    defines the transverse momentum and rapidity for top ad anti-top.

  - `default_jet_parameters` (dictionary): A mapping containing the default values for `nmaxjet`, `p` and `R`.

  - `scales_info` (string): A short description of the default scales

  - `muR0` (string): The default renormalisation scale expressed in terms of a predefined variable.

  - `muF0` (string): The default factorisation scale expressed in terms of a predefined variable.

  - `pdf_set` (string): The default PDF set.

  - `pdf_member` (string): The default PDF member.

  - `contribution_groups` (dictionary): A mapping of contributions to the sub-contributions.

  - `available_pdfs` (dictionary): Detailed information about PDF sets available for this process, potentially containing specialised process specific PDFs. The additional information is used by the `hightea.client` package to automatise PDF uncertainty estimations.



Writing expressions
-------------------

Several API parameters (`cuts`, `muR`, `muF`, `custom_variables`) involve *expressions*. These correspond to mathematical functions of the variables. Expressions are written using the conventions of the Python language (e.g. the  operator `**` is used for exponents and function calls use parenthesis). Expressions admit:
  - References to particle momenta for the  particles defined in the layout (e.g. `p_tbar_0`).
  - References to the predefined variables for the process.
  - References to `custom_variables`.
  - Mathematical operations such as `+`, `/` or `**`.
  - Parenthesis.
  - Arithmetic and trigonometric functions such as  `sqrt` or `log` or `min`.

The HighTEA CLI
===============

An alternative way to interact with the HighTEA API is the `highteacli` command-line-interface. This executable should available after installation of the `hightea-client` package.

The basic workflow consists on providing requests in the [JSON](https://www.json.org/json-en.html) format as input and then analysing the resulting output.

The most frequent command is:

```
highteacli hist <PROCESS NAME> <PATH TO THE JSON FILE FROM THE CURRENT DIRECTORY>
```

For 1D histograms, you can add the `--plot` argument to obtain a quick visualization of the result.

Available processes (to fill in `<PROCESS NAME>`) can be queried with

```
highteacli lproc
```

The format of the input is described in detail in the API section, and [examples](https://github.com/HighteaCollaboration/hightea-examples) are provided.

For example a computing the `y` distribution of the top quark in a top-quark pair production process can be achieved with the following file input (`test.json`):

``` json
{
  "observables": [
    {
      "binning":{
        "variable": "y_t",
        "bins": [-2,-1,0,1,2],
      }
    }
  ]
}
```

Now we can query the 13 TeV top-quark pair dataset as follows

```
$ highteacli hist pp_tt_13000_172.5 test.json
Processing request. The token is cb7a4c94edea11ea8bc49d8a216f62d5.
Wait for the result here or run

    highteacli token cb7a4c94edea11ea8bc49d8a216f62d5

-Token completed
Result written to cb7a4c94edea11ea8bc49d8a216f62d5.json
```

Each successful invocation of the command generates an unique id, *token* that is associated to the requested computation. With the default options, the token name is used to generate the filename.

You can recover data on an existing token, possibly with a simple visualization for 1D histograms, which will be written in the current directory.

```
$ highteacli token --plot cb7a4c94edea11ea8bc49d8a216f62d5
|Token completed
Result written to cb7a4c94edea11ea8bc49d8a216f62d5.json
/
Histogram plot writen to cb7a4c94edea11ea8bc49d8a216f62d5.png

```

The full set of options can be seen with the `--help` flag.

```
$ highteacli --help
```

And specific help for each command can be obtained with
```
$ highteacli --help <COMMAND>`
```
