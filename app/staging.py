import app.smrtlink as smrtlink
from os import listdir, mkdir, makedirs, link, path, rename
from os.path import join, basename, dirname
import shutil

root = '/tmp/staging'

def stage_dataset(dir, dataset):
    if dataset.is_super: # type(files) is dict
        for sample_dir_basename, filepaths in dataset.files.items():
            sample_dir = join(dir, sample_dir_basename)
            mkdir(sample_dir)
            for filepath in filepaths:
                link(filepath, join(sample_dir, basename(filepath)))
    else: # type(files) is list
        for filepath in dataset.files:
            link(filepath, join(dir, basename(filepath)))

def delete_dir(path):
    if path.exists([path]):
        shutil.rmtree(path)

def new(project):
    project_dir = join(root, str(project.id), project.name)
    makedirs(project_dir)
    for uuid in project.dataset_ids:
        dataset = smrtlink.get_client().get_dataset(uuid)
        if not dataset:
            continue
        dataset_dir = join(project_dir, dataset.name)
        mkdir(dataset_dir)
        stage_dataset(dataset_dir, dataset)

def update(project):
    project_path = join(root, project.id, project.name)
    if 'name' in project.updates:
        # change project directory name
        new_project_path = join(dirname(project_path), project.name)
        rename(project_path, new_project_path)
    if 'dataset_ids' in project.updates:
        pass # compare staged datasets to project datasets
        updated_dataset_names = [smrtlink.get_client().get_dataset(uuid) for uuid in project.dataset_ids]
        project_path = join(project_path, project.name)
        dataset_folders = [data_set_folder for data_set_folder in listdir(project_path) if path.isdir(path.join(project_path, data_set_folder))]
        for dataset in updated_dataset_names:
            if dataset not in dataset_folders:
                dataset_dir = join(project_path, dataset.name)
                mkdir(dataset_dir)
                stage_dataset(dataset_dir, dataset)
        for dataset in dataset_folders:
            dataset_path = join(project_path, dataset.name)
            if dataset not in updated_dataset_names:
                delete_dir(dataset_path)
    if 'members' in project.updates:
        pass # compare ?
        # adding or removing access rules