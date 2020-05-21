from pyteomics import mzxml, mzml, mgf
from collections import namedtuple
import csv
import argparse
import subprocess
import sys
from pathlib import Path
import gzip

Spectrum = namedtuple('Spectrum', 'nativeid mslevel ms2plusindex')

def arguments():
    parser = argparse.ArgumentParser(description='Generate index from spectrum file')
    parser.add_argument('-i','--input_spectrum', type = str, help='Single spectrum file of types mzML, mzXML, or mgf.')
    parser.add_argument('-o','--output_folder', type = str, help='Folder to write out tab-separated index file to write out')
    parser.add_argument('-l','--default_ms_level', type = str, help='Default MSlevel')
    parser.add_argument('-e','--suppress_error_text', help='Suppress Errors in Output', dest='suppress_errors', action='store_true')
    parser.set_defaults(suppress_errors=False)
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    return parser.parse_args()

def main():
    args = arguments()

    input = Path(args.input_spectrum)

    input_filetype = ''.join(input.suffixes)

    print(input_filetype)
    output = Path(args.output_folder).joinpath(input.name.replace(input_filetype, '.scans'))

    # List of output spectra
    spectra = []

    # Initialize MS2+ index at 0
    ms2plus_scan_idx = 0

    # In the highly unlikely chance that there are MS1 scans in the MGF set warning flag
    mgf_ms1_warn = False

    if input_filetype == '.mzXML':
        try:
            with open(input, 'rb') as mzxml_file:
                with mzxml.read(mzxml_file) as reader:
                    for s in reader:
                        # Always use scan= for nativeID for mzXML
                        spectra.append(Spectrum('scan={}'.format(s['num']),int(s['msLevel']),-1 if int(s['msLevel']) == 1 else ms2plus_scan_idx))
                        # Increment MS2+ counter, if spectrum was MS2+
                        if int(s.get('msLevel',2)) > 1:
                            ms2plus_scan_idx += 1
        except Error as e:
            if suppress_errors:
                raise Exception("{} is an malformatted {} file.".format(input,input_filetype))
            else:
                raise Exception(e)
    elif input_filetype == '.mzML':
        try:
            with open(input, 'rb') as mzml_file:
                mzml_object = mzml.read(mzml_file)
                param_groups = {}
                for ref in mzml_object.iterfind("referenceableParamGroupList/referenceableParamGroup"):
                    param_groups[ref['id']] = ref
            with open(input, 'rb') as mzml_file:
                with mzml.read(mzml_file) as reader:
                    for s in reader:
                        ms_level = s.get('ms level')
                        if not ms_level:
                            spec_param_group = s.get('ref')
                            if spec_param_group:
                                ms_level = param_groups[spec_param_group].get('ms level')
                            elif args.default_ms_level:
                                ms_level = args.default_ms_level
                            else:
                                raise Exception("No ms level found and no default for input.")
                        # Always use given nativeID for mzML
                        spectra.append(Spectrum(s['id'],int(ms_level),-1 if int(ms_level) == 1 else ms2plus_scan_idx))
                        # Increment MS2+ counter, if spectrum was MS2+
                        if int(ms_level) > 1:
                            ms2plus_scan_idx += 1
        except Error as e:
            if suppress_errors:
                raise Exception("{} is an malformatted {} file.".format(input,input_filetype))
            else:
                raise Exception(e)
    elif input_filetype == '.mzML.gz':
        try:
            with gzip.open(input, 'rb') as mzmlgz_file:
                mzml_object = mzml.read(mzml_file)
                param_groups = {}
                for ref in mzml_object.iterfind("referenceableParamGroupList/referenceableParamGroup"):
                    param_groups[ref['id']] = ref
            with gzip.open(input, 'rb') as mzmlgz_file:
                with mzml.read(mzmlgz_file) as reader:
                    for s in reader:
                        ms_level = s.get('ms level')
                        if not ms_level:
                            spec_param_group = s.get('ref')
                            if spec_param_group:
                                ms_level = param_groups[spec_param_group].get('ms level')
                            elif args.default_ms_level:
                                ms_level = args.default_ms_level
                            else:
                                raise Exception("No ms level found and no default for input.")
                        # Always use given nativeID for mzML
                        spectra.append(Spectrum(s['id'],int(ms_level),-1 if int(ms_level) == 1 else ms2plus_scan_idx))
                        # Increment MS2+ counter, if spectrum was MS2+
                        if int(ms_level) > 1:
                            ms2plus_scan_idx += 1
        except Error as e:
            if suppress_errors:
                raise Exception("{} is an malformatted {} file.".format(input,input_filetype))
            else:
                raise Exception(e)
    elif input_filetype == '.mgf':
        # try to parse this mgf file with the pyteomics library
        try:
            all_scan_idx = 0
            with open(input) as mgf_file:
                with mgf.read(mgf_file) as reader:
                    for s in reader:
                        # Check for MSLEVEL but assume 2
                        ms_level = int(s['params'].get('mslevel', 2))

                        scan_num = s['params'].get('scans')
                        if scan_num:
                            # If SCANS is in the mgf, then use scan= nativeID format
                            native_id = ','.join('scan={}'.format(s) for s in scan_num.split(','))
                        else:
                            # Format as an index= nativeID
                            native_id = 'index={}'.format(all_scan_idx)

                        spectra.append(Spectrum(native_id,ms_level,-1 if ms_level == 1 else ms2plus_scan_idx))

                        # In the highly unlikely chance that there are MS1 scans in the MGF increment global scan idx
                        all_scan_idx += 1

                        if ms_level > 1:
                            ms2plus_scan_idx += 1
        # if that didn't work, just grep for total spectrum count
        except:
            spectra = []
            process = subprocess.Popen(['grep', '-c', 'BEGIN', input], stdout=subprocess.PIPE)
            ms2_count = int(process.communicate()[0])
            # assume all spectra are MS level 2 and write out one row for each
            for index in range(0, ms2_count):
                spectra.append(Spectrum('index={}'.format(index), 2, index))

        # Check if there are extra scans, that aren't MS2+
        if ms2plus_scan_idx < all_scan_idx:
            print("MS1s found in MGF file, proceed with caution!")

    with open(output, 'w') as f:
        r = csv.writer(f, delimiter = '\t')
        for spectrum in spectra:
            r.writerow(list(spectrum))

if __name__ == "__main__":
    main()
