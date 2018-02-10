
#The parameter style in this file is different when the parameters correspond to MOAparameters directly (camel case vs underscores).

from os.path import expanduser
HOME_DIR = expanduser("~")

#HOME_DIR = '/home/chait'
MOA_DIR = '{home_dir}/execmoa'.format(home_dir = HOME_DIR)
OUTPUT_DIR = '{home_dir}/exp_dir/output'.format(home_dir = HOME_DIR)
FIG_DIR = '{home_dir}/exp_dir/figures'.format(home_dir = HOME_DIR)
OUTPUT_PREFIX = 'out'

#MOA_STUMP = "java -cp commons-math3-3.6.1.jar:guava-22.0.jar:moa.jar:cdgen3.jar -javaagent:sizeofag-1.0.0.jar"
MOA_STUMP = "java -cp commons-math3-3.6.1.jar:guava-22.0.jar:moa.jar:cdgen3.jar"

NUM_STREAMS = 10
INDEX_COL = 'learning evaluation instances'

# java -cp commons-math3-3.6.1.jar:moa.jar:cdgen.jar -javaagent:sizeofag-1.0.0.jar moa.gui.GUI

