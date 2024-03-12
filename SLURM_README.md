# Running Conformance Tests on SLURM Clusters
Note: Singularity Cache directories may need to be specified:\
[toil-wdl-runner](https://giwiki.gi.ucsc.edu/index.php?title=Slurm_Tips_for_Toil)\
[Cromwell](https://cromwell.readthedocs.io/en/stable/tutorials/Containers/#singularity-cache)\
[MiniWDL](https://github.com/chanzuckerberg/miniwdl/blob/6dfe83781f74a8e248727eb61c31e1c7562bd26e/tests/singularity.t#L29)
## Under Cromwell
Running on SLURM (and other clusters) may require more arguments/options to be passed into the runners.
\
A [configuration file](https://cromwell.readthedocs.io/en/stable/Configuring/) must be used to tell Cromwell how to schedule workers under SLURM.
An example configuration file is in [cromwell-config.conf](examples/cromwell-config.conf). This file specifies to Cromwell how to run in SLURM with Singularity.
\
The configuration file is then passed into the runner through `--cromwell-pre-args` (not `--cromwell-args` as this must be passed into Java, not Cromwell).
```commandline
python run.py --runner cromwell --id tut01 --cromwell-pre-args="-Dconfig.file=examples/cromwell-config.conf"
```
## Under MiniWDL
The [MiniWDL Slurm plugin](https://github.com/miniwdl-ext/miniwdl-slurm) can be used to run MiniWDL in SLURM with Singularity.
\
The plugin can be [installed](https://github.com/miniwdl-ext/miniwdl-slurm?tab=readme-ov-file#installation) like any other MiniWDL plugin.
\
MiniWDL then needs to be [configured](https://github.com/miniwdl-ext/miniwdl-slurm?tab=readme-ov-file#configuration) to use this extension. This can be done through a configuration file or through environmental variables.
An example configuration file is in [miniwdl-config.cfg](examples/miniwdl-config.cfg).
\
No arguments are needed to be passed into MiniWDL as long as MiniWDL is able to read the new configuration.
An example if MiniWDL specific arguments must be used:
```commandline
python run.py --runner miniwdl --id tut01 --miniwdl-args="--cfg=examples/miniwdl-config.cfg"
```
However, if running the script under an srun launched interactive terminal, this will not work.
\
This is likely because `miniwdl_slurm` runs [srun itself](https://github.com/miniwdl-ext/miniwdl-slurm/blob/624ab390ea872082798733fefbb327dec99e2cde/src/miniwdl_slurm/__init__.py#L97-L100), instead of sbatch, and nested srun's dont appear to work (likely something related to the nested srun asking for more resources beyond the scope of the parent srun).
\
On Phoenix, this can be avoided by running the scripts from mustard, emerald, crimson, razzmatazz, or the head node (but this is probably not recommended).
## Under toil-wdl-runner
`toil-wdl-runner` has [SLURM support built in](https://toil.readthedocs.io/en/latest/running/hpcEnvironments.html#running-on-slurm).
\
SLURM worker partition sizes can be specified with `--partition` or with `TOIL_SLURM_ARGS`.
For example, `export TOIL_SLURM_ARGS="--time=00:30:00 --partition=short"`. [See an example of how to format it](https://giwiki.gi.ucsc.edu/index.php?title=Phoenix_WDL_Tutorial#Running_at_larger_scale).
\
Under certain clusters (ex: Phoenix), Toil may try to create a jobstore at a location not accessible by all workers. `--jobstore-path` can be used to control the jobstore parent directory. It can be an absolute or relative path to `run.py`.
```commandline
python run.py --runner toil-wdl-runner --id tut01 --toil-args="--batchSystem=slurm --batchLogsDir ./slurm_logs --clean=always" --jobstore-path=/path/to/shared_dir"
```
`--clean` and `--batchLogsDir` are not necessarily required, but `--clean` is included to clean excess cruft from failing tests and `--batchLogsDir` is to keep around SLURM logs.