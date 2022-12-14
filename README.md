HighTEA client
==============

User software for interacting with the HighTEA database from the Centre for
Precision Studies in Particle Physics. See High-energy Theory Event Analysis:

http://www.precision.hep.phy.cam.ac.uk/hightea/

and the physics publication:

ARXIV

For a quick start, we recommed new users to have a look at the examples and
tutorial that can be found here:
[hightea-examples](https://github.com/HighteaCollaboration/hightea-examples).

Installation
------------

This package consists of a python library `hightea-client` and the
command-line-interface `highteacli` and is available on
[pip](https://www.pypa.io/en/latest/):

```
pip install hightea-client
```

This should make the executable `highteacli` available. The python library
interface can be included via `import hightea.client`.

A documentation of the library is available here TODO. The documentation
of the command-line-interface is given below.


Basic Usage of CLI
------------------

Once the `highteacli` executable is installed in an accessible
location, the basic workflow consists on providing files in the
[JSON](https://www.json.org/json-en.html) format as input and then
analyzing the resulting output.

The most frequent command is:

```
highteacli hist <PROCESS NAME> <PATH TO THE JSON FILE FROM THE CURRENT DIRECTORY>
```

For 1D histograms, you can add the `--plot` argument to obtain a quick
visualization of the result.

Available processes (to fill in `<PROCESS NAME>`) can be queried with

```
highteacli lproc
```

The format of the input is described in detail in the API section, and
[examples] are provided.

For example a computing the `y` distribution of the top quark in a `t
tbar` production process can be achieved with the following file input (`test.json`):

```json
{
    "binning": [
        {"variable": "y_t",
         "bins": [-2,-1,0,1,2]
        }
    ]
}
```

Now we can query the `tests` ttbar dataset as follows

```
$ highteacli hist tests test.json 
Processing request. The token is cb7a4c94edea11ea8bc49d8a216f62d5.
Wait for the result here or run

    highteacli token cb7a4c94edea11ea8bc49d8a216f62d5

-Token completed
Result written to cb7a4c94edea11ea8bc49d8a216f62d5.json
```

Each successful invocation of the command generates an unique id, *token* that
is associated to the requested computation. With the default options, the token
name is used to generate the filename.

You can recover data on an existing token, possibly with a simple
visualization for 1D histograms, which will be written in the current
directory.

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

The HighTEA API
----------------
Through the interface the users makes web requests to the HighTEA database
service, which provides the following APIs:

  - ``api/processes``: Returns a key-value map where the keys are the
    identifiers for the available processes and the value is the short
    description of the process. The identifying keys are to be used in
    subsequent API calls to retrieve metadata or perform analysis on the
    process. For example browsing to
    `https://www.hep.phy.cam.ac.uk/hightea/api/processes/` yields
    ```json
    {
      "processes/tests":"ttbar test data",
      "processes/pp_jx_7TeV":"pp -> j + X at 7 TeV",
      "processes/pp_aax_8TeV":"pp -> a a + X at 8 TeV",
      "processes/pp_ttx_13TeV":"pp -> t tbar +X at 13 TeV with mt = 172.5 GeV"
    }
    ```
    This API call takes no parameters.


  - ``api/proceses/<PROCESS NAME>`` Returns a key-value
    mapping with the metadata for the process with identifier `<PROCESS NAME>`.
    Details about the metadata provided can be found below.

    This API call takes no parameters.

  - `api/processes/<PROCESS NAME>/make_hist` Returns an histogram for the given
    process based on the user input.

    The API call must be made using the POST
    request method and contain data as a JSON key value pair which conforms to the
    following schema:
      * `"binning"` (required, list of bins specifications): A list of key value
        pairs, each containing:
          - `"variable"`: Variable in which to  bin.
          - `"bins"`: An ordered list of numbers defining the edges of the
              bins. The literal `Infinity` is allowed (as it is `- Infinity`).

        The resulting histogram will correspond to the outer product of all the
        bin specifications in the list.
      * `"custom_variables"` (optional, key value mapping): A map of names to
        expressions in terms of preexisting variables or particle momenta. The
        variables defined here become available for usage in bin specifications
        and filters. The syntax is described in more detail below.
      * `"cuts"` (optional, list of cuts): A list of inequalities between
        expressions. The histogram will only consider events for which the
        inequalities are fulfilled. The syntax is described in more detail below.
      * `"pdf"` (optional, string): The PDF set to be used to reweigh the events.
         If given, $\alpha_S$ and the scales will be evaluated to match the new
        set. Note that this will slow down the computation.
      * `"muR"` (optional, string): An expression corresponding to the
        renormalization scale used for reweighing.
      * `"muR"` (optional, string): An expression corresponding to the
        renormalization scale used for reweighing.
      * `"contributions"` (list of strings, optional): A subset of the
        contributions in a process. If specified, only the weights
        associated to the listed contributions will be taken into
        account.

    An example of a valid request payload is:
    ```json
    {

        "custom_variables": {"circle": "sqrt(pt_top**2 + pt_tbar**2)"},

        "cuts": ["y_tbar <  4", "pt_tbar > 10"],

        "pdf": "CT14nnlo",

        "muR": "2*muR0",

        "muF": "2*muF0",

        "binning": [
           {
            "variable": "circle",
            "bins": [0, 20, 40, 60, 80, Infinity]
           },
           {
            "variable": "pt_ttbar",
            "bins": [0, 20, 40, 60, 80, Infinity]
           }
        ]

    }
    ```

  - `api/available_pdfs`: Returns a list with the available PDFs that
     can be used for reweighting.


A documentation of the API can also be accessed
[here](https://www.hep.phy.cam.ac.uk/hightea/docs).



Description of metadata
-----------------------

    The returned mapping includes (but it is not restricted to) the following
    keys:
      * `name` (string): The short description of the process.
      * `layout`(list): A specification of the particles available for analysis.
        Currently the  valid specifications for an item in the lists are:
          - A key value pair `"particle_momenta": <NAME OF THE PARTICLE>`. This indicates
            that the momenta of the listed particles are available for analysis:
            They are available as variables of the form `p_<NAME OF THE
            PARTICLE>_<u>` where `<u>` is the 4-momentum index, one of {0, 1, 2, 3}. The
            index 0 corresponds to the energy, the indexes 1 and 2 correspond to the
            transverse momentum and the index 3 corresponds the longitudinal
            momentum. (TODO: Specify frame in the metadata).
         - A key value set containing "variable". This represents an
           extra piece of information available for each subevent, which can be
           accessed as a variable, for the purposes of histogramming
           or reweighting, as described below.
        For example
        ```json
        "layout": [
            {"particle_momenta": "t"},
            {"particle_momenta": "tbar"},
            {"variable": "muR0", "description": "Original renormalization scale"},
            {"variable": "muF0", "description": "Original factorization scale"}
        ]
        ```
        in the top pair production process means that the variable `p_t_0` is
        the energy of the top quark and `p_tbar_3` is the longitudinal momentum
        of the antitop quark. Additionally the original scales of each
        subevent are present, so they can easily be accessed to
        produce scale variations around them.
        TODO: This has to be extended to actually allow for jets.
      * `variables` (map of string to string): A mapping of variable names to
         expressions, corresponding to the default predefined variables
         available in the analysis.  For example

         ```json
         "variables": {
             "pt_top": "sqrt(p_t_1**2 + p_t_2**2)",
             "pt_tbar": "sqrt(p_tbar_1**2 + p_tbar_2**2)",
             "y_t": "0.5*log((p_t_0 + p_t_3)/(p_t_0 - p_t_3))",
             "y_tbar": "0.5*log((p_tbar_0 + p_tbar_3)/(p_tbar_0 - p_tbar_3))"
         }
         ```
         defines the transverse momentum and rapidity for top ad antitop.


Writing expressions
-------------------

Several API parameters (filters, extra variables) involve *expressions*. These
correspond to mathematical functions of the variables. Expressions are written
using the conventions of the Python language (e.g. the  operator `**` is used
for exponents and function calls use parenthesis). Expressions admit:

  - References to particle momenta for the  particles defined in the layout (e.g. `p_tbar_0`).
  - References to the predefined variables for the process.
  - References to extra variables.
  - Mathematical operations such as `+`, `/` or `**`.
  - Parenthesis.
  - Arithmetic and trigonometric functions such as  `sqrt`   or `log` or `min`.
