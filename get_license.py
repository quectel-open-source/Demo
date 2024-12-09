#!/usr/bin/env python3
# coding=utf-8
# Inspired by gregory.peng
# Description: check license for yocto build

import sys
import logging
import xlsxwriter
from pathlib import Path
import os
import json
import argparse
import hashlib


class RunConf:

    def __init__(self):
        self.license_path = Path()
        self.filter_path = Path()
        self.out_excel = ""
        self.do_filter = False

    @staticmethod
    def from_args():
        """
            @return: RunConf
        """

        parser = argparse.ArgumentParser(description='get licenses')

        parser.add_argument('license_dir', metavar='license_dir', type=str)

        parser.add_argument('-f', dest='filter_path', type=str,
                            default=str(Path(__file__).parent.joinpath('filter.json')),   
                            help="filter path, default: filter.json")

        parser.add_argument('-o', dest='excel', type=str,
                            default='license.xlsx',   
                            help="out excel, default: license.xlsx")

        # quectel add to control whether to filter
        parser.add_argument('--filter', action='store_true', 
                            help="control whether to filter, default: False")

        args = parser.parse_args()

        conf = RunConf()
        conf.license_path = Path(args.license_dir)
        conf.filter_path = Path(args.filter_path)
        conf.out_excel = args.excel
        conf.do_filter = args.filter

        return conf


class Logger(object):
    def __init__(self,logger_name='license'):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel('WARNING')
        self.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.console_level = 'WARNING'
        self.file_level = 'WARNING'

    def get_Logger(self, log_path: Path):
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.console_level)
            console_handler.setFormatter(self.formatter)
            currentPath = os.getcwd().replace('\\','/') 
            # logger_path = str(log_path) + "/license_log.txt"
            logger_path = currentPath + "/license_log.txt"
            if os.path.exists(logger_path):
                os.remove(logger_path)
            file_handler = logging.FileHandler(logger_path)
            file_handler.setLevel(self.file_level)
            file_handler.setFormatter(self.formatter)
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

        return self.logger


class Getlicense(Logger):
    def __init__(self, license_path: Path, filter_path=None):
        super().__init__()
        self.license_path = license_path
        self.logger = super().get_Logger(license_path)

        if isinstance(filter_path, Path):
            with filter_path.open(mode='r', encoding='utf-8') as f:
                filter_json = json.load(f)
                self.start_key_list = filter_json['filter']['license_name']['start']
                self.include_key_list = filter_json['filter']['license_name']['include']
                self.end_key_list = filter_json['filter']['license_name']['end']
                self.license_txt_list = filter_json['filter']['license_name']['license_txt']
                self.license_key_list = filter_json['filter']['recipeinfo']['LICENSE']
                self.pr_key_list = filter_json['filter']['recipeinfo']['PR']
                self.pv_key_list = filter_json['filter']['recipeinfo']['PV']
                self.url_key_list = filter_json['filter']['recipeinfo']['URL']
        else:
            self.start_key_list = []
            self.include_key_list = []
            self.end_key_list = []
            self.license_txt_list = []
            self.license_key_list = []
            self.pr_key_list = []
            self.pv_key_list = []
            self.url_key_list = []

    def Recipe_exist(self, license_path):
        """
            separate this from File_filter by quectel
        """
        file_list = os.listdir(str(license_path))
        if 'recipeinfo' not in file_list:
            self.logger.error('Filter:the %s have no recipeinfo'%license_path.name)
            return False
        return True

    def Getinfo(self, do_filter: bool):
        license_list = []
        recipe_list = self.GetMachineRecipeList()
        if self.license_path.is_dir():
            for license_dir in self.license_path.iterdir():
                if license_dir.is_dir() and self.Recipe_exist(license_dir):
                    license_info = {}
                    if not do_filter or self.File_filter(license_dir, recipe_list):
                        license_info = self.Getmessage(license_dir)
                        if license_info:
                            license_list.append(license_info)
        else:
            self.logger.error('the licenses file not exists')
        return license_list

    def GetMachineRecipeList(self):
        """
            Filter those recipe names in license.manifest
        """
        recipe_name = "RECIPE NAME: " 
        machine_recipe_list = [] 
        file_glob_search = list(self.license_path.rglob("license.manifest")) 
        for lic_dir in file_glob_search:
            manifest_name = str(lic_dir)
            with open(manifest_name) as f:
                for line in f.readlines():
                    lineinfo = line.strip() 
                    if recipe_name in lineinfo:
                        name = lineinfo[len(recipe_name):]
                        if name not in machine_recipe_list:
                            machine_recipe_list.append(name)
        return machine_recipe_list

    def File_filter(self, license_path, recipe_list: list):
        package_name = license_path.name
        if package_name not in recipe_list:
            self.logger.error('Filter:the %s not in the license.manifest'%(package_name))
            return False
        if self.start_key_list:
            for key in self.start_key_list:
                if package_name.startswith(key):
                    self.logger.error('Filter:the %s begin with %s'%(package_name,key))
                    return False
        if self.include_key_list:
            for key in self.include_key_list:
                if key in package_name:
                    self.logger.error('Filter:the %s include %s'%(package_name,key))
                    return False
        if self.end_key_list:
            for key in self.end_key_list:
                if package_name.endswith(key):
                    self.logger.error('Filter:the %s end with %s'%(package_name,key))
                    return False
        for file in license_path.iterdir():
            if file.name == 'recipeinfo':
                with file.open(mode='r',encoding='utf-8') as f:
                    for line in f.readlines():
                        if 'LICENSE' in line:
                            for key in self.license_key_list:
                                if key in line.lower():
                                    self.logger.warning('Filter:the %s license have LICENSE word %s'%(package_name,key))
                                    return False
                        elif 'PR' in line:
                            for key in self.pr_key_list:
                                if key in line.lower():
                                    self.logger.warning('Filter:the %s license have PR word %s'%(package_name,key))
                                    return False
                        elif 'PV' in line:
                            for key in self.pv_key_list:
                                if key in line.lower():
                                    self.logger.warning('Filter:the %s license have PV word %s'%(package_name,key))
                                    return False
                        elif 'URL' in line:
                            for key in self.url_key_list:
                                if key in line.lower():
                                    self.logger.warning('Filter:the %s license have URL word %s'%(package_name,key))
                                    return False
            
        return True

    def Getmessage(self,path):
        license_dirt = {}
        license_dirt['license_txt'] = ''
        license_md5 = []
        for file in path.iterdir():
            if file.name == 'recipeinfo':
                with file.open(mode='r',encoding='utf-8') as f:
                    license_info = []
                    for line in f.readlines():
                        if 'LICENSE' in line:
                            license_info.append(line.replace('LICENSE:','').strip())
                        elif 'PR' in line:
                            license_info.append(line.replace('PR:','').strip())
                        elif 'PV' in line:
                            license_info.append(line.replace('PV:','').strip())
                        elif 'URL' in line:
                            license_info.append('\n'.join(line.replace('URL:','').split()).strip())
                        elif 'TYPE' in line:
                            package_type = self.Gettype(line)
                            license_info.append(package_type)
                    license_dirt['info'] = license_info
                    license_dirt['name'] = path.name
            else: 
                try:
                    with file.open(mode='r',encoding='utf-8') as f1:
                        license_txt = f1.read()
                        md5hash = hashlib.md5(license_txt.encode(encoding='utf-8')).hexdigest()
                        if md5hash not in license_md5:
                            license_md5.append(md5hash)
                            license_dirt['license_txt'] += license_txt
                except:
                    with file.open(mode='r',encoding='ISO-8859-1') as f1:
                        license_txt = f1.read()
                        license_dirt['license_txt'] += license_txt
        return license_dirt

    def Gettype(self,type_info):
        type_list = type_info.split()
        libs_num = 0 
        bins_num = 0
        for i in range(len(type_list)):
            if type_list[i] == 'libs':
                libs_num = int(type_list[i+1])
            elif type_list[i] == 'bins':
                bins_num = int(type_list[i+1])
        if libs_num > 0 :
            if bins_num > 0:
                package_type = 'dynamically linked library & Binary'
            else:
                package_type = 'dynamically linked library'
        elif bins_num > 0:
            package_type = 'Binary'
        else:
            package_type = 'Other'
        return package_type


class Createxcel(Logger):
    def __init__(self, excel_path: Path):
        super().__init__('excel')
        self.excel_path = excel_path
        self.logger = super().get_Logger(os.path.dirname(excel_path))
        if os.path.exists(self.excel_path):
            self.logger.warning('the license.xlsx have exists')
            os.remove(self.excel_path)
        self.excel = xlsxwriter.Workbook(self.excel_path)

    def Excelstyle(self):
        self.style_header = self.excel.add_format({
            'bold':  True,
            'border':1, 
            'font_size':12,
            'align':'top',        
            'valign': 'vcenter',        
            'text_wrap': True   
        })
        self.style = self.excel.add_format({
            'bold':  False,       
            'border':1,        
            'font_size':12,
            'align':'left',          
            'valign':'vcenter',         
            'text_wrap': True,     
        })
        self.sheet = self.excel.add_worksheet('license')
        self.sheet.set_column('A:B',20)
        self.sheet.set_column('C:D',12)
        self.sheet.set_column('E:F',30)
        self.sheet.set_column('G:G',55)

    def run(self, license_path: Path, filter_path=None, do_filter=True):
        self.Excelstyle()
        headers = ['OSS Module Name','Version of the OSS','Licenses & Version', 'URL','Copyright Notice and License Texts']
        self.sheet.write_row('A1',headers,self.style_header)
        formater = self.excel.add_format({'border':1})
        license_info = Getlicense(license_path, filter_path).Getinfo(do_filter)
        begin_row = 1
        for i in range(len(license_info)):
            self.sheet.write(begin_row+i,0,license_info[i]['name'],self.style)
            self.sheet.write(begin_row+i,1,license_info[i]['info'][0],self.style)
            try:
                self.sheet.write(begin_row+i,2,license_info[i]['info'][2],self.style)
            except:
                self.sheet.write(begin_row+i,2,'',self.style)
            # use write_string instead of write to fix a error of url exceeds 255 by quectel
            try:
                self.sheet.write_string(begin_row+i,3,license_info[i]['info'][3],self.style)
            except:
                self.sheet.write_string(begin_row+i,3,'',self.style)
            self.sheet.write(begin_row+i,4,license_info[i]['license_txt'],self.style)
        self.excel.close()
        print('ALL done')


if __name__ == '__main__':
    
    conf = RunConf.from_args()

    Createxcel(conf.out_excel).run(conf.license_path, conf.filter_path, conf.do_filter)
