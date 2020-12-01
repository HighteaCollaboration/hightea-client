HighTea client
==============

A quick command line interface for the database for the Events Bases Library
from the Centre for Precision Studies in Particle Physics.


See A Theory-Events-Based Library of LHC Processes:

http://www.precision.hep.phy.cam.ac.uk/events-based-library/

Installation
------------

The package is available on [pip](https://www.pypa.io/en/latest/):

```
pip install highteacli
```

Basic Usage
-----------

Once the `hightea` executable is installed in an accessible
location, the basic workflow consists on providing files in the
[JSON](https://www.json.org/json-en.html) format as input and then
analyzing the resulting output.


The most frequent command is:

```
hightea hist <PROCESS NAME> <PATH TO THE JSON FILE FROM THE CURRENT DIRECTORY>
```

For 1D histograms, you can add the `--plot` argument to obtain a quick
visualization of the result.

Available processes (to fill in `<PROCESS NAME>`) can be queried with

```
hightea lproc
```

The format of the input is described in detail in the [documentation], and
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
$ hightea hist tests test.json 
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
$ hightea token --plot cb7a4c94edea11ea8bc49d8a216f62d5
|Token completed
Result written to cb7a4c94edea11ea8bc49d8a216f62d5.json
/
Histogram plot writen to cb7a4c94edea11ea8bc49d8a216f62d5.png

```




The full set of options can be seen with the `--help` flag.



```
$ hightea --help
```

And specific help for each command can be obtained with
```
$ hightea --help <COMMAND>`

```

