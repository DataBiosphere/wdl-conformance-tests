# Running Conformance Tests on Slulrm Clusters
## Singularity Cache
Note: For Singularity, Singularity Cache directories may need to be specified:\
[toil-wdl-runner](https://giwiki.gi.ucsc.edu/index.php?title=Slurm_Tips_for_Toil)\
[Cromwell](https://cromwell.readthedocs.io/en/stable/tutorials/Containers/#singularity-cache)\
[MiniWDL](https://github.com/chanzuckerberg/miniwdl/blob/6dfe83781f74a8e248727eb61c31e1c7562bd26e/tests/singularity.t#L29)

Docker should handle cache by itself.
## Under Cromwell
Running on Slurm (and other clusters) may require more arguments/options to be passed into the runners.

A [configuration file](https://cromwell.readthedocs.io/en/stable/Configuring/) must be used to tell Cromwell how to schedule workers under Slurm.
An example configuration file is in [cromwell-config.conf](examples/cromwell-config.conf). This file specifies to Cromwell how to run in Slurm with Singularity.

The configuration file is then passed into the runner through `--cromwell-pre-args` (not `--cromwell-args` as this must be passed into Java, not Cromwell).
```commandline
python run.py --runner cromwell --id tut01 --cromwell-pre-args="-Dconfig.file=examples/cromwell-config.conf"
```

For Slurm+Docker, the [configuration file](examples/cromwell-config.conf) includes an example configuration, but this has not been fully tested. `backend.default` can be replaced with `SLURM` instead.

## Under MiniWDL
The [MiniWDL Slurm plugin](https://github.com/miniwdl-ext/miniwdl-slurm) can be used to run MiniWDL in SLURM with Singularity.

The plugin can be [installed](https://github.com/miniwdl-ext/miniwdl-slurm?tab=readme-ov-file#installation) like any other MiniWDL plugin.

MiniWDL then needs to be [configured](https://github.com/miniwdl-ext/miniwdl-slurm?tab=readme-ov-file#configuration) to use this extension. This can be done through a [configuration file or through environmental variables](https://miniwdl.readthedocs.io/en/latest/runner_reference.html?highlight=config#configuration).
An example configuration file is in [miniwdl-config.cfg](examples/miniwdl-config.cfg). 

No arguments are needed to be passed into MiniWDL as long as MiniWDL is able to read the new configuration.

However, if wanted, arguments can be used instead:
```commandline
python run.py --runner miniwdl --id tut01 --miniwdl-args="--no-outside-imports"
```
However, if running the script under an srun launched interactive session, this will not work.

This is likely because `miniwdl_slurm` runs [srun itself](https://github.com/miniwdl-ext/miniwdl-slurm/blob/624ab390ea872082798733fefbb327dec99e2cde/src/miniwdl_slurm/__init__.py#L97-L100) instead of sbatch, and nested srun's dont appear to work (likely something related to the nested srun asking for more resources beyond the scope of the parent srun).

Thus, the performance tests should be invoked in a parent/external node. [(An example for Phoenix cluster.)](SLURM_PHOENIX_README.md#under-miniwdl).

A Slurm+Docker plugin does not currently exist.

## Under toil-wdl-runner
`toil-wdl-runner` has [Slurm support built in](https://toil.readthedocs.io/en/latest/running/hpcEnvironments.html#running-on-slurm).

Slurm worker partition sizes can be specified with `--partition` or with `TOIL_SLURM_ARGS`.
For example, `export TOIL_SLURM_ARGS="--time=00:30:00 --partition=short"`. [See an example of how to format it](https://giwiki.gi.ucsc.edu/index.php?title=Phoenix_WDL_Tutorial#Running_at_larger_scale).

Toil communicates with a jobstore that must be accessible to all worker nodes, so some [extra arguments](SLURM_README.md#under-toil-wdl-runner) may be necessary depending on how each cluster is configured.
```commandline
python run.py --runner toil-wdl-runner --id tut01 --toil-args="--batchSystem=slurm --batchLogsDir ./slurm_logs --clean=always"
```
`--clean` and `--batchLogsDir` are not necessarily required, but `--clean` is included to clean excess cruft from failing tests and `--batchLogsDir` is to keep around SLURM logs.

If using Docker instead of Singularity, `--container=docker` should be included in `--toil-args`.