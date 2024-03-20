# Running Conformance Tests on the Phoenix Slurm Cluster
This is an addendum to [`SLURM_README.md`](SLURM_README.md) and contains some small notes on how to run conformance tests for the Phoenix cluster.

For Singularity, the Singularity cache directories must be configured [as mentioned](SLURM_README.md#singularity-cache).
## Under Cromwell
No extra configuration should be necessary.

## Under MiniWDL
Additional note to:
```
However, if running the script under an srun launched interactive terminal, this will not work.

This is likely because `miniwdl_slurm` runs [srun itself](https://github.com/miniwdl-ext/miniwdl-slurm/blob/624ab390ea872082798733fefbb327dec99e2cde/src/miniwdl_slurm/__init__.py#L97-L100) instead of sbatch, and nested srun's dont appear to work (likely something related to the nested srun asking for more resources beyond the scope of the parent srun).
```
On Phoenix, this can be avoided by running the scripts from mustard, emerald, crimson, razzmatazz. (The Phoenix head node can also be used, but this is not probably not recommended.)

## Under toil-wdl-runner
There are Slurm tips for Toil that may be helpful.
- [General tips](https://giwiki.gi.ucsc.edu/index.php?title=Slurm_Tips_for_Toil)
- [Phoenix tips](https://giwiki.gi.ucsc.edu/index.php?title=Phoenix_WDL_Tutorial)
- [Toil documentation](https://toil.readthedocs.io/en/latest/running/hpcEnvironments.html#running-on-slurm)


Under certain clusters (ex: Phoenix), Toil may try to create a jobstore at a location not accessible by all workers. `--jobstore-path` can be used to control the jobstore parent directory. It can be an absolute or relative path to `run.py`.

```commandline
python run.py --runner toil-wdl-runner --id tut01 --toil-args="--batchSystem=slurm --batchLogsDir ./slurm_logs --clean=always" --jobstore-path=/path/to/shared_dir"
```