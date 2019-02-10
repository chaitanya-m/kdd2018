
import os, shutil

#Folder Utilities
def remove_folder(path):
  if(os.path.exists)(path):
    shutil.rmtree(path)
  return

def make_folder(path):
  try:
    os.stat(path)
  except:
    os.mkdir(path)
  return



