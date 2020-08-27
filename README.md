HighTea cli
===========

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

Once the `highteacli` executable is installed in an accessible
location, the basic workflow consists on providing files in the
[JSON](https://www.json.org/json-en.html) format as input and then
analyzing the resulting output.


The most frequent command is:

```
highteacly hist <PROCESS NAME> <PATH TO THE JSON FILE FROM THE CURRENT DIRECTORY>
```

The format is described in detail in the [documentation], and
[examples] are provided.

For example a computing the `y` distribution of the top quark in a `t
tbar` production process can be achieved with the following file input (`test.json`):

```
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
 Processing request. The token is 866dd3c269f211eaa66d0242ac120003.
 Wait for the result here or run
 highteacli token 866dd3c269f211eaa66d0242ac120003
 Token completed
 {"mean": [[[[-2.0, -1.0]], 297.7068930126204], [[[-1.0, 0.0]], -165.29122920133463], [[[0.0, 1.0]], 202.0481155648153], [[[1.0, 2.0]], 301.92919831259667]], "std": [[[[-2.0, -1.0]], 225.39857447188203], [[[-1.0, 0.0]], 305.63359250045437], [[[0.0, 1.0]], 297.698081581902], [[[1.0, 2.0]], 240.26288960758953]]}
```

The JSON output can be easily redirected to a file for further
processing:

```
highteacli hist tests test.json  > res.json
```


The full set of options can be seen with the `--help` flag.



```
$ highteacli --help
usage: highteacli.py [-h] {lproc,lpdf,hist} ...

A command line interface for the high energy theory database.

optional arguments:
  -h, --help         show this help message and exit

commands:
  {lproc,lpdf,hist}
    lproc            List available processes
    lpdf             List available pdfs
    hist             make and histogram

```

And specific help for each command can be obtained with `highteacli
--help <COMMAND>`

```
 $ python highteacli.py hist --help
usage: highteacli.py hist [-h] process file

positional arguments:
  process     process to compute the histogram for
  file        JSON file with the hisogram specification

optional arguments:
  -h, --help  show this help message and exit

```

