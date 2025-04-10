import logging
import multiprocessing as mp
import concurrent.futures
import os
from memory_profiler import profile
import pythia.functions
import pythia.io
import pythia.template
import pythia.plugin
import pythia.util
from multiprocessing import Pool
from concurrent.futures import ProcessPoolExecutor
import time


def build_context(args):

    run, ctx, config = args
    if not config["silence"]:
        print("+", end="", flush=True)
    context = run.copy()
    context = {**context, **ctx}
    y, x = pythia.util.translate_coords_news(context["lat"], context["lng"])
    context["contextWorkDir"] = os.path.join(context["workDir"], y, x)

    for k, v in run.items():
        if "::" in str(v) and k != "sites":
            fn = v.split("::")[0]
            if fn != "raster":
                res = getattr(pythia.functions, fn)(k, run, context, config)
                if res is not None:
                    context = {**context, **res}
                else:
                    context = None
                    break
    return context


def _generate_context_args(runs, peers, config):
    for idx, run in enumerate(runs):
        for peer in peers[idx]:
            yield run, peer, config


def symlink_wth_soil(output_dir, config, context):
    if "include" in context:
        for include in context["include"]:
            if os.path.exists(include):
                include_file = os.path.join(output_dir, os.path.basename(include))
                if not os.path.exists(include_file):
                    os.symlink(os.path.abspath(include), include_file)
    if "weatherDir" in config:
        weather_file = os.path.join(output_dir, "{}.WTH".format(context["wsta"]))
        if not os.path.exists(weather_file):
            os.symlink(
                os.path.abspath(os.path.join(config["weatherDir"], context["wthFile"])),
                os.path.join(weather_file),
            )
    for soil in context["soilFiles"]:
        soil_file = os.path.join(output_dir, os.path.basename(soil))
        if not os.path.exists(soil_file):
            os.symlink(
                os.path.abspath(soil), os.path.join(output_dir, os.path.basename(soil))
            )


def compose_peerless(context, config, env):
    if not config["silence"]:
        print(".", end="", flush=True)
    this_output_dir = context["contextWorkDir"]
    symlink_wth_soil(this_output_dir, config, context)
    xfile = pythia.template.render_template(env, context["template"], context)
    with open(os.path.join(context["contextWorkDir"], context["template"]), "w") as f:
        f.write(xfile)
    return context["contextWorkDir"]

def process_context(context, plugins, config, env):
    if context is not None:
        pythia.io.make_run_directory(context["contextWorkDir"])
        # Post context hook
        logging.debug("[PEERLESS] Running post_build_context plugins")
        context = pythia.plugin.run_plugin_functions(
            pythia.plugin.PluginHook.post_build_context,
            plugins,
            context=context,
        )
        return os.path.abspath(compose_peerless(context, config, env))
    else:
        if not config["silence"]:
            print("K", end="", flush=True)

def execute(config, plugins):
    runs = config.get("runs", [])
    if len(runs) == 0:
        return
    runlist = []
    for run in runs:
        pythia.io.make_run_directory(os.path.join(config["workDir"], run["name"]))
    peers = [pythia.io.peer(r, config.get("sample", None)) for r in runs]

    # pool_size = config.get("threads", mp.cpu_count() * 10)
    pool_size = config.get("threads", mp.cpu_count())
    print("RUNNING WITH POOL SIZE: {}".format(pool_size))
    env = pythia.template.init_engine(config["templateDir"])
    pythia.functions.build_ghr_cache(config)

    with mp.Pool(pool_size) as pool:
        results =  pool.imap_unordered(
            build_context, _generate_context_args(runs, peers, config), 250
        )
        with concurrent.futures.ProcessPoolExecutor(max_workers=pool_size) as executor:
        # Use submit to asynchronously execute the process_context function for each context
            future_to_result = {executor.submit(process_context, context, plugins, config, env): context for context in results}

            # Iterate through the completed futures
            runlist = []
            for future in concurrent.futures.as_completed(future_to_result):
                try:
                    result = future.result()
                    if result is not None:
                        runlist.append(result)
                except Exception as e:
                    # Handle exceptions if any occurred during processing
                    print(f"Error processing context: {e}")
    
    if config["exportRunlist"]:
        with open(os.path.join(config["workDir"], "run_list.txt"), "w") as f:
            [f.write(f"{x}\n") for x in runlist]
    if not config["silence"]:
        print()
