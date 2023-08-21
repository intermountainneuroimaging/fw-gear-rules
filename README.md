# fw-gear-rules
Flywheel python sdk project to build "gear rules" for session level analyses. Project uses a generic json template to define flywheel gear workflow and pass/fail conditions.

## Description
This project provides example code to set up a generic flywheel gear workflow that can be run at any container level (e.g. session, subject, project etc). A provided python script is used to interpret a json template file and apply gear rules to flywheel containers. When run conditions are met, the python script will launch a new analysis job with the provided configuration, inputs, tags, and label. This is currently the best "work around" for session level gear rules in flywheel. 

## Template File
"Gear Rules" and run configurations are set using a json file. The optional and required json dictionary keys are described in detail below.

The json file must contain an `analysis` dictionary key, where all workflow steps are detailed.
```
"__comment__": "example template",
"analysis": 
    [
        {
          <gear template descriptors>
        }
    ]

```
Each "workflow stage" should contain instructions to run a single analysis, include the gear name, version, inputs, config, tags, label and conditions.


### Gear Template Descriptors

#### __comment__ 
(optional) add description of workflow stage or any other relevant comments 
```
"__comment__": "step 1: curate session using bids reproin naming convention"
```
#### gear-name
(required) flywheel gear name used to run analysis
```
"gear-name": "curate-bids"
```
#### gear-version
(optional) flywheel gear version used in current analysis, if this key is excluded, the most recent version of the gear is used.
```
"gear-version":"2.1.3_1.0.7"
```

#### inputs
(optional) if input files are required in the current analysis, each input file should be detailed here. The inputs should be formated in a dictionary format. Each dictionary key must exactly match the input name for the flywheel gear. If you are not sure the input name for the flywheel gear, you can find the placeholder in the gear info. In the example below we are passing two input files, one that will be passed as "template" and a second that will be passed as "freesurfer-license". For each input file, there are additional dictionary settings that can be passed to point to the correct file in flyhweel. 

Two options can be used to point to a file name: (1) `regex` uses python's regular expression syntax to return matching files by regular expression. If more than one file is found, an error will be logged and the current analysis will not run; (2) `value` which will look for an exact filename match in flywheel. It is also required to identify `parent-container` to idenitfy where to go looking for the file (project | subject | session | analysis).

`optional` is an additional flag that is used to either log and error and exit if no file match is found, or proceed without a file match. This can be useful for 'generic' files such as `.bidsignore` which may only be present in some projects.
```
"inputs": {
            "template": {
                "regex": "-reproin-template.json$",
                "parent-container": "project",
                "optional": true
            },
            "freesurfer-license": {
              "value": "license.txt"
              "parent-container": "project",
              "optional": false
            }
        },
```
#### config
(optional) if configuration settings differ from the gear defaults, the configuration for the current analysis is detailed here. The configurations should be written exactly as they appear in the gear info, and must be formated as a dictionary.
```
"config": {
            "reset": true,
            "intendedfor_regexes": ".*fmap.* nii",
            "use_or_save_config": "Ignore Config File"
        },
```


#### tags
(optional) if any tags should be added to the analysis, enter them as a list of strings here
```
"tags": ["hpc"]
```

#### custom-label
(optional) add a custom label for the current analysis. Default label is the gear name followed by current date and time.
```
"custom-label": "completeness-curator"
```

### Other Options - Setting `RUN` conditions

#### prerequisites 
(optional) list of prerequesite gears that must have completed sucessfully before current analysis will run (e.g. curate-bids should always be run *before* bids-mriqc). In addtion, prerequisites checks with look for either "any" sucessful prior gear, or "all" sucessful prior gears. Two use cases: (1) "Any" prerequisite, check for a sucessful bids-fmriprep analysis before running bids-feat as the fmriprep output is used as an input file in bids-feat; (2) "All" prerequisite, check if *all* acquisitions were correctly precurated by checking all bids-pre-curate are completed before running curate-bids.
```
"prerequisites":  {"curate-bids":"any", "hierarchy-curator": "any"}
```
#### count-failures
(optional) by default, the worflow will not re-run gears that are currently running or have completed sucessfully. In the case, were a prior analysis failed, you can automatically re-try the analysis up to the number defined here (e.g. count-failures: 2 ... would re-try the gear once resulting in 2 total attempts).
```
"count-failures": 2
```
#### sleep_seconds
(optional) for some light weight gears, its can be nice to hold the program open for a period of time to check if the gear finishes before proceeding. This is recommended only for light weight gears where downstream analyses are held due to prerequisite conditions.
```
"sleep_seconds": 30
```

#### completeness-tags
(optional) CU Boulder specific metadata tag produced during the completeness curator which details if the session meets a predefined template. For more information on the completeness curator, contact the INC data and analysis team. Boolean metadata tags will be checked for all those passed in a list of strings.
```
"completeness-tags": ["Run Downstream Analyses"]
```


## Cron Job Setup
Once a gear template has been generated for a project, and uploaded to project files in Flywheel, the relevant python run script (e.g. session_auto_run_gears.py) can be set to run on a nightly cron job to check for any new sessions and apply the analysis workflow. Check out our example shell wrappers to ensure logging and timeouts setup for a cron job.
```
0 1 * * * /pl/active/ics/fw_cron_jobs/start-auto_run_gears.sh
```


## Examples

Here are some example gear templates for commonly uses analyses at CU Boulder

#### Curate Bids
```
{
    "__comment__": "step 1: curate session using bids reproin naming convention",
    "gear-name": "curate-bids",
    "gear-version":"2.1.3_1.0.7",
    "inputs": {
        "template": {
            "regex": "-reproin-template.json$",
            "parent-container": "project",
            "optional": true
        }
    },
    "config": {
        "reset": true,
        "intendedfor_regexes": ".*fmap.* nii",
        "use_or_save_config": "Ignore Config File"
    },
    "tags": [],
    "count-failures": 1,
    "sleep_seconds": 30
}
```

#### Hierarchy Curator
```
{
    "__comment__": "step 2: analysis gear hierarchy-curator - session completeness",
    "gear-name": "hierarchy-curator",
    "gear-version":"2.1.4_inc0.2",
    "inputs": {
        "curator": {
            "regex": "_completeness.py$",
            "parent-container": "project"
        },
        "additional-input-one": {
            "regex": "_completeness_template.csv$",
            "parent-container": "project"
        }
    },
    "config": {
        "reset": true
    },
    "tags": [],
    "custom-label": "completeness-curator",
    "count-failures": 1,
    "prerequisites":  {"curate-bids":"any"},
    "sleep_seconds": 30
}
```

#### Bids-MRIQC
```
{
  "__comment__": "step 3: analysis gear bids-mriqc - run for complete sessions",
  "gear-name": "bids-mriqc",
  "gear-version":"1.2.4_22.0.6_inc1.2",
  "inputs": {
      "bidsignore": {
          "value": ".bidsignore",
          "parent-container": "project",
          "optional": true
      }
  },
  "config": {
      "fd_thres": 0.2,
      "gear-dry-run": false,
      "gear-keep-output": false,
      "gear-writable-dir": "/pl/active/ics/fw_temp_data",
      "mem_gb": 16,
      "n_cpus": 4,
      "slurm-cpu": "4",
      "slurm-nodes": "1",
      "slurm-ntasks": "1",
      "slurm-partition": "blanca-ics",
      "slurm-account": "blanca-ics",
      "slurm-qos": "blanca-ics",
      "slurm-ram": "16G",
      "slurm-time": "1428"
  },
  "tags": ["hpc"],
  "count-failures": 2,
  "prerequisites":  {"curate-bids":"any", "hierarchy-curator": "any"},
  "sleep_seconds": 30,
  "completeness-tags": ["Run Downstream Analyses"]
}
```

### BIDS-fMRIPrep
```
{
  "__comment__": "step 4: analysis gear bids-fmriprep - run for complete sessions",
  "gear-name": "bids-fmriprep",
  "gear-version":"1.2.5_23.0.1_inc2.0",
  "inputs": {
      "bidsignore": {
          "value": ".bidsignore",
          "parent-container": "project",
          "optional": true
      },
      "freesurfer_license": {
          "value": "license.txt",
          "parent-container": "project",
          "optional": false
      }
  },
  "config": {
      "gear-dry-run": False,
      "gear-log-level": "DEBUG",
      "gear-writable-dir": "/pl/active/ics/fw_temp_data",
      "mem_mb": 28000,
      "n_cpus": 6,
      "no-submm-recon": False,
      "notrack": False,
      "omp-nthreads": 6,
      "output-spaces": "T1w MNI152NLin2009cAsym MNI152NLin6Asym fsnative",
      "ignore": "slicetiming",
      "skip-bids-validation": True,
      "slurm-cpu": "4",
      "slurm-ram": "28G",
      "verbose": "v",
      "slurm-account": "blanca-ics",
      "slurm-partition": "blanca-ics",
      "slurm-qos": "blanca-ics",
      "slurm-time": "1440",
  },
  "tags": ["hpc"],
  "count-failures": 1,
  "prerequisites":  {"bids-mriqc":"any"},
  "completeness-tags": ["Run Downstream Analyses"]
}
```
