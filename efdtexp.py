
import os
import sys
import utilities
import re
import math
import subprocess
import shlex
import string
import pandas as pd
import simpleExperiments as se
import moa_command_vars as mcv
from multiprocessing import Process, Queue

random_source_str = r'--random-source=<( openssl enc -aes-256-ctr -pass pass:seed -nosalt </dev/zero 2>/dev/null)'

def runexp(learners, generators, evaluators, suffix):
    output_dir = mcv.OUTPUT_DIR + "/" + str(suffix)
    experiments = se.CompositeExperiment.make_experiments(mcv.MOA_STUMP, evaluators, learners, generators)
#---------- Comment these lines out to get just charts
    processes = se.CompositeExperiment.make_running_processes(experiments, output_dir)
    se.Utils.wait_for_processes(processes)
#----------

    error_df = se.Utils.error_df_from_folder(output_dir)
    runtime_dict = se.Utils.runtime_dict_from_folder(output_dir)
    split_df = se.Utils.split_df_from_folder(output_dir)

    new_col_names = ["VFDT", "EFDT"]
    for col in error_df.columns:
        new_col_names[int(col)] = (new_col_names[int(col)] + " | T:" + ("%.2f s"%runtime_dict[col]) + " | E: " + ("%.4f"%error_df[col].mean()))
    error_df.columns = new_col_names

    se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(suffix).zfill(3), None)

def runexp23(learners, generators, evaluators, suffix):
    output_dir = mcv.OUTPUT_DIR + "/" + str(suffix)
    experiments = se.CompositeExperiment.make_experiments(mcv.MOA_STUMP, evaluators, learners, generators)
    processes = se.CompositeExperiment.make_running_processes(experiments, output_dir)
    se.Utils.wait_for_processes(processes)

    error_df = se.Utils.error_df_from_folder(output_dir)
    runtime_dict = se.Utils.runtime_dict_from_folder(output_dir)
    split_df = se.Utils.split_df_from_folder(output_dir)

    new_col_names = ["VFDT2", "VFDT3", "VFDT4", "VFDT5"]#, "EFDT2", "EFDT3", "EFDT4", "EFDT5", ]
    for col in error_df.columns:
        new_col_names[int(col)] = (str(col)+ ": "+ new_col_names[int(col)] + " | T:" + ("%.2f s"%runtime_dict[col]) + " | E: " + ("%.4f"%error_df[col].mean()))
    error_df.columns = new_col_names

    se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(suffix).zfill(3), split_df)

def shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix):

    subprocesses= []
    files = []
    seeded_generators=[]

#================== Run without this in order to not have to redo all the shuffling
    # Generate the shuffled tails for the streams
    for i in range(0, num_streams):

      subprocesses.append(subprocess.Popen(['shuf -o ' + shuf_prefix + str(i) + ' ' + tail_prefix + ' '
	+ string.replace(random_source_str, 'seed', str(i)) ], shell=True, executable = '/bin/bash'))
    # Need executable = /bin/bash, Otherwise it will use /bin/sh, which on Ubuntu is dash, a basic shell that doesn't recognize ( symbols

    exit_codes = [p.wait() for p in subprocesses] # Wait- Ensure all shuffled tails have been created    
    subprocesses = []

#==================

    # Generate the final arffs through concatenation with heads, and the respective generators
    for i in range(0, num_streams):
      files.append(' ' + shuf_prefix + str(i) + '.arff')
      seeded_generators.append(re.sub('(\/.*)+\.arff', files[i], generator_template))


#================== Run without this in order to not have to redo all the shuffling
      print(re.sub('(\/.*)+\.arff', files[i], generator_template))
      subprocesses.append(subprocess.Popen(['cat ' + ' ' + head_prefix + ' ' + 
	' ' + shuf_prefix + str(i) +'>'+ str(files[i])], shell=True, executable = '/bin/bash'))
    exit_codes = [p.wait() for p in subprocesses]
    subprocesses = []
#==================


    # Now run experiments for each learner on all the arffs
    all_processes=[]
    exp_dir = mcv.OUTPUT_DIR + "/" + str(exp_no) 

    os.chdir(mcv.MOA_DIR)
#+++++++++++++++++ Comment this out in order to just draw charts without running experiments
    utilities.remove_folder(exp_dir)
    if not os.path.exists(exp_dir):
      os.makedirs(exp_dir)
####+++++++++++++++++

    lrn_ctr = -1
    output_dirs = []
    for learner in learners:
      lrn_ctr += 1
      singleLearnerList = []
      singleLearnerList.append(learner)
      output_dir = exp_dir + "/" + str(lrn_ctr) 
      output_dirs.append(output_dir)

#+++++++++++++++++ Comment this out in order to just draw charts without running experiments
      seeded_experiments = se.CompositeExperiment.make_experiments(mcv.MOA_STUMP, evaluators, singleLearnerList, seeded_generators)
      processes = se.CompositeExperiment.make_running_processes(seeded_experiments, output_dir)
      all_processes.extend(processes)

      exit_codes = [p.wait() for p in all_processes] # USE THIS ONE FOR FONTS so it doesn't overload RAM. 4Gig per process.
###+++++++++++++++++
    #exit_codes = [p.wait() for p in all_processes]
 


    # List of mean_dataframes
    mean_dataframes = []
    # Dataframe that contains all the mean error columns for the experiments
    error_df = pd.DataFrame([])
    # Dataframe that contains all the mean split columns for the experiments
    split_df = pd.DataFrame([])

    folder_ctr = -1
    # average the streams, then plot
    for folder in output_dirs:
      folder_ctr+=1
      files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
      dataframes = []
      for this_file in files:
        dataframes.append(pd.read_csv(this_file, index_col=False, header=0, skiprows=0))

      all_stream_learning_data = pd.concat(dataframes)
      all_stream_mean = {}
      num_rows = dataframes[0].shape[0] 
      for i in range(num_rows):
        all_stream_mean[i] = all_stream_learning_data[i::num_rows].mean()
      all_stream_mean_df = pd.DataFrame(all_stream_mean).transpose()
    #runexp23(learners, generators, evaluators, 23)
      all_stream_mean_df['error'] = (100.0 - all_stream_mean_df['classifications correct (percent)'])/100.0

      # Only mark actual splits as 1 and discard the rest of the split counts
      splitArray = all_stream_mean_df['splits']
      i = 0
      while i < splitArray.size-1:
        #print(str(i+1) + " " + str(splitArray[i+1]) + "\n")
        diff = math.floor(splitArray[i+1]) - math.floor(splitArray[i])
        if(diff > 0):
          splitArray[i+1] = (-1)*diff
          i = i+2
        else:
          i=i+1
      for i in range(splitArray.size):
        if(splitArray[i] > 0):
          splitArray[i] = 0
        else:
          splitArray[i] = (-1) * splitArray[i]

      # Add this folder's mean error column to the error_df 
      #error_df[str(folder)] = all_stream_mean_df['error'] 
      average_error = all_stream_mean_df['error'].sum()/num_rows
      cpu_time = all_stream_mean_df['evaluation time (cpu seconds)'].iloc[num_rows-1] # yes this is avg cpu_time
      #print("+++++++++++" + str(jkl))
      #error_df[" M: "+ str(folder)+ " | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.7f"%average_error) + ' |'] = all_stream_mean_df['error']
      legend_str = ''
      if folder_ctr == 0:
        legend_str = 'VFDT'
      else:
	legend_str = 'EFDT'

      error_df[legend_str + ": | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.4f"%average_error) + ' |'] = all_stream_mean_df['error']
      #error_df["Classes : "  + os.path.basename(os.path.normpath(folder))+ " | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.7f"%average_error) + ' |'] = all_stream_mean_df['error']
      #error_df[" | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.7f"%average_error) + ' |'] = all_stream_mean_df['error']
      #error_df[str(folder)+" "+"5"] = all_stream_mean_df['error']
      #split_df["splits " + os.path.basename(os.path.normpath(folder))] = all_stream_mean_df['splits']
      split_df["Splits: " + legend_str] = all_stream_mean_df['splits']

      mean_dataframes.append(all_stream_mean_df)

    # Set the index column
    # error_df[mcv.INDEX_COL]
    error_df[mcv.INDEX_COL] = mean_dataframes[0][mcv.INDEX_COL]/1000 # MAGIC NUMBER!!- its the measurement frequency
    error_df = error_df.set_index(mcv.INDEX_COL)
    #error_df.to_csv(mcv.OUTPUT_DIR + "/" + mcv.OUTPUT_PREFIX +  "Error.csv")

    split_df[mcv.INDEX_COL] = mean_dataframes[0][mcv.INDEX_COL]/1000 # MAGIC NUMBER!!
    split_df = split_df.set_index(mcv.INDEX_COL)
    #split_df.to_csv(mcv.OUTPUT_DIR + "/" + mcv.OUTPUT_PREFIX +  "Split.csv")

    #se.Plot.plot_df(error_df, " ", mcv.FIG_DIR+"/"+str(figNo).zfill(3), split_df)
    #se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(exp_no).zfill(3), split_df)
    se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(exp_no).zfill(3), None)

def chart1():

 
    exp_no = 1
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/hepmass/hepmass.arff -c 1)"
    evaluators = [ r"EvaluatePrequential -i 1234567890 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/hepmass/hepmassshuf"
    head_prefix = r"/mnt/datasets/hepmass/hepmasshead"
    tail_prefix = r"/mnt/datasets/hepmass/hepmasstail"
 
    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)



def chart1a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/hepmass/hepmass.arff -c 1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 1234567890 -f 1000 -q 1000"]

    runexp(learners, generators, evaluators, '1a')

def chart2():

    exp_no = 2
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/wisdm/wisdmshuf.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/wisdm/wisdmshuf"
    head_prefix = r"/mnt/datasets/wisdm/wisdmhead"
    tail_prefix = r"/mnt/datasets/wisdm/wisdmtail"
 
    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)

def chart2a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/wisdm/wisdm.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '2a')


def chart3():
 
    exp_no = 3
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template =r"-s (ArffFileStream -f /mnt/datasets/susy/susy.arff -c 1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/susy/susyshuf"
    head_prefix = r"/mnt/datasets/susy/susyhead"
    tail_prefix = r"/mnt/datasets/susy/susytail"
 
    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)


def chart3a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/susy/susy.arff -c 1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '3a')

def chart4():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/airlines.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 4)

def chart5():

    exp_no = 5
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/kddshuf.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/kdd/kddshuf"
    head_prefix = r"/mnt/datasets/kdd/kddhead"
    tail_prefix = r"/mnt/datasets/kdd/kddtail"

    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)

def chart5a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/kdd/KDDCup99_full.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '5a')


def chart6():

    exp_no = '6'
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/higgsc/higgsc.arff -c 1)"
    evaluators = [ r"EvaluatePrequential -i 1234567890 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/higgsc/higgscshuf"
    head_prefix = r"/mnt/datasets/higgsc/higgschead"
    tail_prefix = r"/mnt/datasets/higgsc/higgsctail"

    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)


def chart6a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      #r"-s (ArffFileStream -f /mnt/datasets/higgsOrig.arff -c 33)"
      r"-s (ArffFileStream -f /mnt/datasets/higgsc/higgsc.arff -c 1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 1234567890 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '6a')

def chart7():

    exp_no = '7'
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/harpagwag/harpagwag.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 1234567890 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/harpagwag/harpagwagshuf"
    head_prefix = r"/mnt/datasets/harpagwag/harpagwaghead"
    tail_prefix = r"/mnt/datasets/harpagwag/harpagwagtail"

    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)


def chart7a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/harpagwag/harpagwag.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 1234567890 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '7a')


def chart8():

    exp_no = 8
    num_streams = 10
 
    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/poker/pokershuf.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
 
    shuf_prefix = r"/mnt/datasets/poker/pokershuf"
    head_prefix = r"/mnt/datasets/poker/pokerhead"
    tail_prefix = r"/mnt/datasets/poker/pokertail"

    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)

def chart8a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/poker/poker-lsn.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '8a')

def chart9():

    exp_no = 9
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/cpe/cpe.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/cpe/cpeshuf"
    head_prefix = r"/mnt/datasets/cpe/cpehead"
    tail_prefix = r"/mnt/datasets/cpe/cpetail"

    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)

def chart9a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/cpe/cpe.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '9a')


def chart10():

    exp_no = 10
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/sensor/sensor.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/sensor/sensorshuf"
    head_prefix = r"/mnt/datasets/sensor/sensorhead"
    tail_prefix = r"/mnt/datasets/sensor/sensortail"

    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)

def chart10a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/sensor/sensor.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '10a')



def chart11():

    exp_no = 11
    num_streams = 10
 
    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/covtype/covtypeNorm.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
 
    shuf_prefix = r"/mnt/datasets/covtype/covtypeshuf"
    head_prefix = r"/mnt/datasets/covtype/covtypehead"
    tail_prefix = r"/mnt/datasets/covtype/covtypetail"

    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)

def chart11a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/covtype/covtypeNorm.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '11a')


def chart13():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/airlineshuf.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 13)

def chart14():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/3covtype.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 14)

def chart15():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/3airlines.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 15)

def chart16():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/3wisdm.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 16)
def chart18():

    exp_no = 18
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/skin/skin.arff -c -1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/skin/skinshuf"
    head_prefix = r"/mnt/datasets/skin/skinhead"
    tail_prefix = r"/mnt/datasets/skin/skintail"
    
    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)

def chart18a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/skin/skin.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '18a')


def chart19():

    exp_no = 19
    num_streams = 10

    learners = [ r"-l trees.VFDT", r"-l (trees.EFDT -R 2000)"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/pamap2_9subjectsshuf.arff -c 2)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/pamap2/pamap2_9subjects_shuf"
    head_prefix = r"/mnt/datasets/pamap2/pamap2_9subjects_head"
    tail_prefix = r"/mnt/datasets/pamap2/pamap2_9subjects_tail"
 
    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)


def chart19a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/pamap2/pamap2_9subjects_unshuf.arff -c 2)"
    ]
    evaluators = [ r"EvaluatePrequential -i 200000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '19a')


def chart20():

    exp_no = 20
    num_streams = 10
 
    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generator_template = r"-s (ArffFileStream -f /mnt/datasets/fontshuf.arff -c 1)"
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]

    shuf_prefix = r"/mnt/datasets/fonts/fontsshuf"
    head_prefix = r"/mnt/datasets/fonts/fontshead"
    tail_prefix = r"/mnt/datasets/fonts/fontstail"
 
    shuffledRealExpOps(exp_no, num_streams, learners, generator_template, evaluators, shuf_prefix, head_prefix, tail_prefix)


def chart20a():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/fonts/fonts.arff -c 1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 200000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, '20a')





def chart21():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/chessshuf.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 21)

def chart22():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/chessshufdiscrete.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 22)

def chart23():

    learners = [ r"-l trees.VFDT" ]#, r"-l trees.EFDT"]
    generators = [
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 2 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 3 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 4 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 5 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",

    ]
    evaluators = [ r"EvaluatePrequential -i 100000000 -f 1000 -q 1000" ]
    num_rows = int(100000000/1000)


    all_processes = []
    # get 10 stream average for each generator
    gen_no = 1
    exp_dir = mcv.OUTPUT_DIR + "/" + str(23) 
    output_dirs = []
    for gen_string in generators:
      seeded_generators = []
      gen_no += 1
      output_dir = exp_dir + "/" + str(gen_no) 
      output_dirs.append(output_dir)

      for randomSeed in range(0, 5): #random seed for tree; generate 10 random streams  for this generator
        gen_cmd = re.sub("-r [0-9]+", "-r "+ str(randomSeed)+ " ", str(gen_string))
	#print(gen_cmd)
        seeded_generators.append(gen_cmd)

      seeded_experiments = se.CompositeExperiment.make_experiments(mcv.MOA_STUMP, evaluators, learners, seeded_generators)
#===================Comment these to just generate plots
      processes = se.CompositeExperiment.make_running_processes(seeded_experiments, output_dir)
      all_processes.extend(processes)

    exit_codes = [p.wait() for p in all_processes]
#==================== 
    # List of mean_dataframes
    mean_dataframes = []
    # Dataframe that contains all the mean error columns for the experiments
    error_df = pd.DataFrame([])
    # Dataframe that contains all the mean split columns for the experiments
    split_df = pd.DataFrame([])

    # average the streams, then plot
    for folder in output_dirs:
      files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
      dataframes = []
      for this_file in files:
        dataframes.append(pd.read_csv(this_file, index_col=False, header=0, skiprows=0))

      all_stream_learning_data = pd.concat(dataframes)
      all_stream_mean = {}
      for i in range(num_rows):
        all_stream_mean[i] = all_stream_learning_data[i::num_rows].mean()
      all_stream_mean_df = pd.DataFrame(all_stream_mean).transpose()
    #runexp23(learners, generators, evaluators, 23)
      all_stream_mean_df['error'] = (100.0 - all_stream_mean_df['classifications correct (percent)'])/100.0

      # Only mark actual splits as 1 and discard the rest of the split counts
      splitArray = all_stream_mean_df['splits']
      i = 0
      while i < splitArray.size-1:
        #print(str(i+1) + " " + str(splitArray[i+1]) + "\n")
        diff = math.floor(splitArray[i+1]) - math.floor(splitArray[i])
        if(diff > 0):
          splitArray[i+1] = (-1)*diff
          i = i+2
        else:
          i=i+1
      for i in range(splitArray.size):
        if(splitArray[i] > 0):
          splitArray[i] = 0
        else:
          splitArray[i] = (-1) * splitArray[i]

      # Add this folder's mean error column to the error_df 
      #error_df[str(folder)] = all_stream_mean_df['error'] 
      average_error = all_stream_mean_df['error'].sum()/num_rows
      cpu_time = all_stream_mean_df['evaluation time (cpu seconds)'].iloc[num_rows-1] # yes this is avg cpu_time
      #print("+++++++++++" + str(jkl))
      #error_df[" M: "+ str(folder)+ " | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.7f"%average_error) + ' |'] = all_stream_mean_df['error']
      error_df[" Classes: "+ os.path.basename(os.path.normpath(folder))+ " | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.4f"%average_error) + ' |'] = all_stream_mean_df['error']
      #error_df[" | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.7f"%average_error) + ' |'] = all_stream_mean_df['error']
      split_df["Splits: " + os.path.basename(os.path.normpath(folder)) + " classes"] = all_stream_mean_df['splits']
      #error_df[str(folder)+" "+"5"] = all_stream_mean_df['error']

      mean_dataframes.append(all_stream_mean_df)

    # Set the index column
    # error_df[mcv.INDEX_COL]
    error_df[mcv.INDEX_COL] = mean_dataframes[0][mcv.INDEX_COL]/1000 #MAGIC
    error_df = error_df.set_index(mcv.INDEX_COL)
    #error_df.to_csv(mcv.OUTPUT_DIR + "/" + mcv.OUTPUT_PREFIX +  "Error.csv")

    split_df[mcv.INDEX_COL] = mean_dataframes[0][mcv.INDEX_COL]/1000 #MAGIC
    split_df = split_df.set_index(mcv.INDEX_COL)
    #split_df.to_csv(mcv.OUTPUT_DIR + "/" + mcv.OUTPUT_PREFIX +  "Split.csv")

    #se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(23).zfill(3), split_df)
    se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(23).zfill(3), None)


def chart24():

    learners = [ r"-l (trees.EFDT)"]
    generators = [
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 2 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 3 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 4 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",
            r"-s (generators.RandomTreeGenerator -r 1 -i 1 -c 5 -o 5 -u 0 -v 5 -d 5 -l 3 -f 0.15)",

    ]
    evaluators = [ r"EvaluatePrequential -i 100000000 -f 1000 -q 1000" ]
    num_rows = int(100000000/1000) #MAGIC NUMBER


    all_processes = []
    # get 10 stream average for each generator
    gen_no = 1
    exp_dir = mcv.OUTPUT_DIR + "/" + str(24) 
    output_dirs = []
    for gen_string in generators:
      seeded_generators = []
      gen_no += 1
      output_dir = exp_dir + "/" + str(gen_no) 
      output_dirs.append(output_dir)

      for randomSeed in range(0, 5): #random seed for tree; generate 10 random streams  for this generator
        gen_cmd = re.sub("-r [0-9]+", "-r "+ str(randomSeed)+ " ", str(gen_string))
	#print(gen_cmd)
        seeded_generators.append(gen_cmd)

      seeded_experiments = se.CompositeExperiment.make_experiments(mcv.MOA_STUMP, evaluators, learners, seeded_generators)
#===================Comment these to just generate plots
      processes = se.CompositeExperiment.make_running_processes(seeded_experiments, output_dir)
      all_processes.extend(processes)

    exit_codes = [p.wait() for p in all_processes]
#=================== 
    # List of mean_dataframes
    mean_dataframes = []
    # Dataframe that contains all the mean error columns for the experiments
    error_df = pd.DataFrame([])
    # Dataframe that contains all the mean split columns for the experiments
    split_df = pd.DataFrame([])

    # average the streams, then plot
    for folder in output_dirs:
      files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
      dataframes = []
      for this_file in files:
        dataframes.append(pd.read_csv(this_file, index_col=False, header=0, skiprows=0))

      all_stream_learning_data = pd.concat(dataframes)
      all_stream_mean = {}
      for i in range(num_rows):
        all_stream_mean[i] = all_stream_learning_data[i::num_rows].mean()
      all_stream_mean_df = pd.DataFrame(all_stream_mean).transpose()
    #runexp24(learners, generators, evaluators, 24)
      all_stream_mean_df['error'] = (100.0 - all_stream_mean_df['classifications correct (percent)'])/100.0

      # Only mark actual splits as 1 and discard the rest of the split counts
      splitArray = all_stream_mean_df['splits']
      i = 0
      while i < splitArray.size-1:
        #print(str(i+1) + " " + str(splitArray[i+1]) + "\n")
        diff = math.floor(splitArray[i+1]) - math.floor(splitArray[i])
        if(diff > 0):
          splitArray[i+1] = (-1)*diff
          i = i+2
        else:
          i=i+1
      for i in range(splitArray.size):
        if(splitArray[i] > 0):
          splitArray[i] = 0
        else:
          splitArray[i] = (-1) * splitArray[i]

      # Add this folder's mean error column to the error_df 
      #error_df[str(folder)] = all_stream_mean_df['error'] 
      average_error = all_stream_mean_df['error'].sum()/num_rows
      cpu_time = all_stream_mean_df['evaluation time (cpu seconds)'].iloc[num_rows-1] # yes this is avg cpu_time
      #print("+++++++++++" + str(jkl))
      #error_df[" M: "+ str(folder)+ " | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.7f"%average_error) + ' |'] = all_stream_mean_df['error']
      error_df[" Classes: "+ os.path.basename(os.path.normpath(folder))+ " | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.4f"%average_error) + ' |'] = all_stream_mean_df['error']
      #error_df[" | T: " + ("%.2f"%cpu_time) + 's | ' + " E:" + ("%.7f"%average_error) + ' |'] = all_stream_mean_df['error']
      split_df["Splits: " + os.path.basename(os.path.normpath(folder)) + " classes"] = all_stream_mean_df['splits']
      #error_df[str(folder)+" "+"5"] = all_stream_mean_df['error']

      mean_dataframes.append(all_stream_mean_df)

    # Set the index column
    # error_df[mcv.INDEX_COL]
    error_df[mcv.INDEX_COL] = mean_dataframes[0][mcv.INDEX_COL]/1000 #MAGIC NUMBER
    error_df = error_df.set_index(mcv.INDEX_COL)
    #error_df.to_csv(mcv.OUTPUT_DIR + "/" + mcv.OUTPUT_PREFIX +  "Error.csv")

    split_df[mcv.INDEX_COL] = mean_dataframes[0][mcv.INDEX_COL]/1000 #MAGIC NUMBER
    split_df = split_df.set_index(mcv.INDEX_COL)
    #split_df.to_csv(mcv.OUTPUT_DIR + "/" + mcv.OUTPUT_PREFIX +  "Split.csv")

    #se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(24).zfill(3), split_df)
    se.Plot.plot_df(error_df, "Error", mcv.FIG_DIR+"/"+str(24).zfill(3), None)

def chart26():

    learners = [ r"-l trees.VFDT", r"-l (trees.EFDT -R 2000)"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/pamap2/pamap2_9subjects_unshuf.arff -c 2)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 26)

def chart28():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/chess.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 28)

def chart29():

    learners = [ r"-l trees.VFDT", r"-l trees.EFDT"]
    generators = [
      r"-s (ArffFileStream -f /mnt/datasets/chessshufdiscrete.arff -c -1)"
    ]
    evaluators = [ r"EvaluatePrequential -i 20000000 -f 1000 -q 1000"]
    runexp(learners, generators, evaluators, 29)


    # without the main sentinel below code will always get run, even when imported as a module!
if __name__=="__main__": 

    processes = {}


#    processes['5'] = Process(target=chart5)   # kddshuf = use rangehigh 0.025 for this
#    processes['5a'] = Process(target=chart5a) # kdd98 = use 0.7, halve linewidth and increase dash diff size
#
#    processes['8'] = Process(target=chart8)   # pokershuf = 0.7
#    processes['8a'] = Process(target=chart8a)   # poker = 0.7
#
#    processes['18'] = Process(target=chart18) # Skin shuffled = 0.15
#    processes['18a'] = Process(target=chart18a) # Skin = 0.15
# 
#    processes['11'] = Process(target=chart11) # covtype shuffled = 0.7
#    processes['11a'] = Process(target=chart11a) # covtype Normalised = 0.7
#
#    processes[20] = Process(target=chart20) # Font shuffled = This requires a one-line-change in shuffledRealExpOps- run 10 processes at a time, not 20- takes too much memory!! 0.15
#    processes['20a'] = Process(target=chart20a)  # Fonts = 1.0

#    processes[2] = Process(target=chart2)   # wisdmshuf = 0.7
#    processes['2a'] = Process(target=chart2a)   # wisdm = 0.7

#    processes[19] = Process(target=chart19) # PAMAP2 9 subjects shuffled = 0.7
#    processes['19a'] = Process(target=chart19a) # PAMAP2 = 1.0

#    processes[7] = Process(target=chart7) # HAR shuffled = 0.7
#    processes['7a'] = Process(target=chart7a) # HAR = 1.0

#    processes[6] = Process(target=chart6) # Higgs shuffled = 0.7
#    processes['6a'] = Process(target=chart6a) # Higgs = 0.7
###This is so, so big that it breaks python. Make sure suffling and file creation works manually.


#    processes[1] = Process(target=chart1)   # hepmass shuffled = 0.7
#    processes['1a'] = Process(target=chart1a)   # hepmass = 0.7

#    processes[3] = Process(target=chart3)   # susy = 0.7
#    processes['3a'] = Process(target=chart3a)   # susy = 0.7

#    processes[9] = Process(target=chart9)   # sensor = 0.7
#    processes['9a'] = Process(target=chart9a)   # sensor = 0.7


#    processes[10] = Process(target=chart10)   # sensor = 0.7
#    processes['10a'] = Process(target=chart10a)   # sensor = 0.7

#    processes[23] = Process(target=chart23) # Synthetic VFDT nominal
#    processes[24] = Process(target=chart24) # Synthetic EFDT nominal

    #processes[28] = Process(target=chart28)  # Chess

    for key in processes:
      processes[key].start()
   
