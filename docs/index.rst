.. HighTea documentation master file, created by
   sphinx-quickstart on Tue Dec  1 19:56:32 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to hightea-client's documentation!
==========================================

This documentation provides information about the "hightea-client" python library, allowing interaction with HighTEA API. This library consists of two parts: the lower-level "API" class, which helps perform low-level interaction with the API, and the higher-level client "Interface" class, which implements a simple command paradigm for creating and submitting requests to the API. For working examples, please refer to the HighTEA-examples repository (https://github.com/HighteaCollaboration/hightea-examples).

Additionally the documentation of the DataHandler class used internally for the computation of systematic uncertainties is provided.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Interface class
===============

.. automodule:: hightea.client.interface
    :members:


DataHandler class
=================

.. automodule:: hightea.client.datahandler
    :members:

API class
=========

.. automodule:: hightea.client.apiactions
    :members:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
