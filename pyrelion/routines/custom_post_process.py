#
#    Copyright (C) 2023 CCP-EM
#
#    This Source Code Form is subject to the terms of the Mozilla
#    Public License, v. 2.0. If a copy of the MPL was not
#    distributed with this file, You can obtain one at
#    https://mozilla.org/MPL/2.0/
#

import os
from glob import glob
from typing import List, Dict, Sequence, Tuple, Union

from pipeliner.pipeliner_job import PipelinerCommand
from pipeliner.jobs.relion.relion_job import relion_program, RelionJob
from pipeliner.data_structure import (
    POSTPROCESS_JOB_NAME,
    POSTPROCESS_DIR,
)
from pipeliner.nodes import (
    NODE_DENSITYMAP,
    NODE_PROCESSDATA,
    NODE_MASK3D,
    NODE_LOGFILE,
    NODE_MICROSCOPEDATA,
)
from pipeliner.job_options import (
    InputNodeJobOption,
    FileDescription,
    EXT_RELION_HALFMAP,
    EXT_MRC_MAP,
    BooleanJobOption,
    FloatJobOption,
    JobOptionCondition,
    JobOptionValidationResult,
)
from pipeliner.display_tools import (
    graph_from_starfile_cols,
    create_results_display_object,
    make_maps_slice_montage_and_3d_display,
)
from pipeliner.starfile_handler import StarFile
from pipeliner.results_display_objects import ResultsDisplayObject, ResultsDisplayGraph


class CustomPostprocessJob(RelionJob):

    PROCESS_NAME = POSTPROCESS_JOB_NAME
    OUT_DIR = POSTPROCESS_DIR
    CATEGORY_LABEL = "Map Postprocessing"

    def __init__(self) -> None:
        super().__init__()
        self.always_continue_in_schedule = True
        self.can_continue = True
        self.jobinfo.programs = [
            relion_program("relion_postprocess", emdb_categories=["MASKING"])
        ]
        self.jobinfo.display_name = "RELION post-processing"

        self.jobinfo.short_desc = (
            "Create a sharpened and masked map from refinement results"
        )
        self.jobinfo.long_desc = (
            "After performing a 3D auto-refinement, the map needs to be sharpened."
            " Also, the gold-standard FSC curves inside the auto-refine procedures only"
            " use unmasked maps (unless you’ve used the option Use solvent-flattened"
            " FSCs). This means that the actual resolution is under-estimated during"
            " the actual refinement, because noise in the solvent region will lower the"
            " FSC curve. Relion’s procedure for B-factor sharpening and calculating"
            " masked FSC curves is called post-processing."
        )

        self.joboptions["fn_in"] = InputNodeJobOption(
            label="One of the 2 unfiltered half-maps:",
            node_type=NODE_DENSITYMAP,
            node_kwds=["halfmap"],
            default_value="",
            pattern=FileDescription("MRC halfmap files", EXT_RELION_HALFMAP),
            help_text="An unfiltered halfmap from a Relion refinement job",
            is_required=True,
            validation_regex="^.+half.+$",
            regex_error_message="Must be in Relion format; contain 'half'",
        )

        self.joboptions["fn_mask"] = InputNodeJobOption(
            label="Solvent mask:",
            node_type=NODE_MASK3D,
            default_value="",
            pattern=FileDescription("Mask MRC file", EXT_MRC_MAP),
            help_text="A soft edged mask file with values from 0-1",
            is_required=True,
        )

        self.joboptions["angpix"] = FloatJobOption(
            label="Calibrated pixel size (A)",
            default_value=-1.0,
            suggested_min=0.3,
            suggested_max=5,
            step_value=0.1,
            help_text=(
                "Provide the final, calibrated pixel size in Angstroms. This value may"
                " be different from the pixel-size used thus far, e.g. when you have"
                " recalibrated the pixel size using the fit to a PDB model. The X-axis"
                " of the output FSC plot will use this calibrated value."
            ),
            in_continue=True,
            is_required=True,
        )

        self.joboptions["do_auto_bfac"] = BooleanJobOption(
            label="Estimate B-factor automatically?",
            default_value=True,
            help_text=(
                "If set to Yes, then the program will use the automated procedure"
                " described by Rosenthal and Henderson (2003, JMB) to estimate an"
                " overall B-factor for your map, and sharpen it accordingly. Note that"
                " your map must extend well beyond the lowest resolution included in"
                " the procedure below, which should not be set to resolutions much"
                " lower than 10 Angstroms."
            ),
            in_continue=True,
        )
        self.joboptions["autob_lowres"] = FloatJobOption(
            label="Lowest resolution for auto-B fit (A):",
            default_value=10,
            suggested_min=8,
            suggested_max=15,
            step_value=0.5,
            help_text=(
                "This is the lowest frequency (in Angstroms) that will be included in"
                " the linear fit of the Guinier plot as described in Rosenthal and"
                " Henderson (2003, JMB). Dont use values much lower or higher than 10"
                " Angstroms. If your map does not extend beyond 10 Angstroms, then"
                " instead of the automated procedure use your own B-factor."
            ),
            in_continue=True,
            deactivate_if=JobOptionCondition([("do_auto_bfac", "=", False)]),
            required_if=JobOptionCondition([("do_auto_bfac", "=", True)]),
        )
        # user is allowed option to select to conflicting options here could simplify
        self.joboptions["do_adhoc_bfac"] = BooleanJobOption(
            label="Use your own B-factor?",
            default_value=False,
            help_text=(
                "Instead of using the automated B-factor estimation, provide your own"
                " value. Use negative values for sharpening the map.This option is"
                " useful if your map does not extend beyond the 10A needed for the"
                " automated procedure, or when the automated procedure does not give a"
                " suitable value (e.g. in more disordered parts of the map)."
            ),
            in_continue=True,
            deactivate_if=JobOptionCondition([("do_auto_bfac", "=", True)]),
        )
        self.joboptions["adhoc_bfac"] = FloatJobOption(
            label="User-provided B-factor:",
            default_value=-1000,
            suggested_min=-2000,
            suggested_max=0,
            step_value=-50,
            help_text=(
                "Use negative values for sharpening. Be careful: if you over-sharpen"
                " your map, you may end up interpreting noise for signal!"
            ),
            in_continue=True,
            deactivate_if=JobOptionCondition([("do_auto_bfac", "=", True)]),
            required_if=JobOptionCondition([("do_auto_bfac", "=", False)]),
        )

        self.joboptions["fn_mtf"] = InputNodeJobOption(
            label="MTF of the detector (STAR file)",
            default_value="",
            node_type=NODE_MICROSCOPEDATA,
            node_kwds=["mtf"],
            pattern=FileDescription("STAR Files", [".star"]),
            help_text=(
                "If you know the MTF of your detector, provide it here. Curves for some"
                " well-known detectors may be downloaded from the RELION Wiki. Also see"
                " there for the exact format. If you do not know the MTF of your"
                " detector and do not want to measure it, then by leaving this entry"
                " empty, you include the MTF of your detector in your overall estimated"
                " B-factor upon sharpening the map. Although that is probably slightly"
                " less accurate, the overall quality of your map will probably not"
                " suffer very much."
            ),
            in_continue=True,
        )
        self.joboptions["mtf_angpix"] = FloatJobOption(
            label="Original detector pixel size:",
            default_value=-1.0,
            suggested_min=0.3,
            suggested_max=2.0,
            step_value=0.1,
            help_text=(
                "This is the original pixel size (in Angstroms) in "
                "the raw (non-super-resolution!) micrographs."
            ),
            in_continue=True,
            required_if=JobOptionCondition([("fn_mtf", "!=", "")]),
            deactivate_if=JobOptionCondition([("fn_mtf", "=", "")]),
        )
        self.joboptions["do_skip_fsc_weighting"] = BooleanJobOption(
            label="Skip FSC-weighting?",
            default_value=False,
            help_text=(
                "If set to No (the default), then the output map will be low-pass"
                " filtered according to the mask-corrected, gold-standard FSC-curve."
                " Sometimes, it is also useful to provide an ad-hoc low-pass filter"
                " (option below), as due to local resolution variations some parts of"
                " the map may be better and other parts may be worse than the overall"
                " resolution as measured by the FSC. In such cases, set this option to"
                " Yes and provide an ad-hoc filter as described below."
            ),
            in_continue=True,
        )
        self.joboptions["low_pass"] = FloatJobOption(
            label="Ad-hoc low-pass filter (A):",
            default_value=5,
            suggested_min=1,
            suggested_max=40,
            step_value=1,
            help_text=(
                "This option allows one to low-pass filter the map at a user-provided"
                " frequency (in Angstroms). When using a resolution that is higher than"
                " the gold-standard FSC-reported resolution, take care not to interpret"
                " noise in the map for signal..."
            ),
            in_continue=True,
            required_if=JobOptionCondition([("do_skip_fsc_weighting", "=", True)]),
            deactivate_if=JobOptionCondition([("do_skip_fsc_weighting", "=", False)]),
        )

        self.get_runtab_options(addtl_args=True)

    def create_output_nodes(self) -> None:
        self.add_output_node(
            "postprocess.mrc", NODE_DENSITYMAP, ["relion", "postprocess"]
        )
        self.add_output_node(
            "postprocess_masked.mrc",
            NODE_DENSITYMAP,
            ["relion", "postprocess", "masked"],
        )
        self.add_output_node(
            "postprocess.star", NODE_PROCESSDATA, ["relion", "postprocess"]
        )
        self.add_output_node("logfile.pdf", NODE_LOGFILE, ["relion", "postprocess"])

    def get_commands(self) -> List[PipelinerCommand]:

        self.command = ["relion_postprocess"]
        mask = self.joboptions["fn_mask"].get_string()

        self.command += ["--mask", mask]

        fn_half1 = self.joboptions["fn_in"].get_string()

        self.command += ["--i", fn_half1]
        self.command += ["--o", self.output_dir + "postprocess"]

        angpix = self.joboptions["angpix"].get_string()
        self.command += ["--angpix", angpix]

        do_auto_bfac = self.joboptions["do_auto_bfac"].get_boolean()
        do_adhoc_bfac = self.joboptions["do_adhoc_bfac"].get_boolean()

        if do_auto_bfac:
            autob_lowres = self.joboptions["autob_lowres"].get_string()
            self.command += ["--auto_bfac", "--autob_lowres", autob_lowres]

        elif do_adhoc_bfac:
            adhoc_bfac = self.joboptions["adhoc_bfac"].get_string()
            self.command += ["--adhoc_bfac", adhoc_bfac]

        fn_mtf = self.joboptions["fn_mtf"].get_string()
        mtf_angpix = self.joboptions["mtf_angpix"].get_string()
        if len(fn_mtf) != 0:
            self.command += ["--mtf", fn_mtf, "--mtf_angpix", mtf_angpix]

        do_skip_fsc_weighting = self.joboptions["do_skip_fsc_weighting"].get_boolean()
        low_pass = self.joboptions["low_pass"].get_string()
        if do_skip_fsc_weighting:
            self.command += ["--skip_fsc_weighting", "--low_pass", low_pass]

        other_args = self.joboptions["other_args"].get_string()
        if len(other_args) > 0:
            self.command += self.parse_additional_args()

        return [PipelinerCommand(self.command, relion_control=True)]

    def additional_joboption_validation(self) -> List[JobOptionValidationResult]:
        do_auto_bfac = self.joboptions["do_auto_bfac"].get_boolean()
        do_adhoc_bfac = self.joboptions["do_adhoc_bfac"].get_boolean()
        if not do_auto_bfac and not do_adhoc_bfac:
            return [
                JobOptionValidationResult(
                    result_type="error",
                    raised_by=[
                        self.joboptions["do_auto_bfac"],
                        self.joboptions["do_adhoc_bfac"],
                    ],
                    message="Must select one",
                )
            ]
        return []

    def prepare_clean_up_lists(self, do_harsh=False) -> Tuple[List[str], List[str]]:
        """Return list of intermediate files/dirs to remove"""

        del_files = glob(self.output_dir + "*masked.mrc")
        return del_files, []

    def gather_metadata(
        self,
    ) -> Dict[str, Union[int, float, str, bool, dict, list, None]]:
        fsc_file = os.path.join(self.output_dir, "postprocess.star")
        gendat = StarFile(fsc_file).get_block("general")
        res = float(gendat.find_value("_rlnFinalResolution"))
        bf = float(gendat.find_value("_rlnBfactorUsedForSharpening"))
        map1 = gendat.find_value("_rlnUnfilteredMapHalf1")
        map2 = gendat.find_value("_rlnUnfilteredMapHalf2")
        mask = gendat.find_value("_rlnMaskName")
        rand = float(gendat.find_value("_rlnRandomiseFrom"))
        slope = float(gendat.find_value("_rlnFittedSlopeGuinierPlot"))
        intercept = float(gendat.find_value("_rlnFittedInterceptGuinierPlot"))
        corr = float(gendat.find_value("_rlnCorrelationFitGuinierPlot"))

        metadata_dict: Dict[str, Union[int, float, str, bool, dict, list, None]] = {}
        metadata_dict["FinalResolution"] = res
        metadata_dict["BfactorUsedForSharpening"] = bf
        metadata_dict["UnfilteredMapHalf1"] = map1
        metadata_dict["UnfilteredMapHalf2"] = map2
        metadata_dict["MaskName"] = mask
        metadata_dict["RandomiseFrom"] = rand
        metadata_dict["FittedSlopeGuinierPlot"] = slope
        metadata_dict["FittedInterceptGuinierPlot"] = intercept
        metadata_dict["CorrelationFitGuinierPlot"] = corr

        return metadata_dict

    def create_results_display(self) -> Sequence[ResultsDisplayObject]:
        fsc_file = os.path.join(self.output_dir, "postprocess.star")
        disp_objs = []
        gendat = StarFile(fsc_file).get_block("general")
        res = float(gendat.find_value("_rlnFinalResolution"))
        bf = gendat.find_value("_rlnBfactorUsedForSharpening")
        disp_objs.append(
            create_results_display_object(
                "table",
                title="PostProcessed map info",
                headers=["Resolution:", f"{round(res, 2)} Å"],
                table_data=[["Sharpening b-factor:", f"{bf}"]],
                associated_data=[fsc_file],
            )
        )
        # prepare the map
        out_map = {
            os.path.join(self.output_dir, "postprocess_masked.mrc"): "Postprocessed "
            "and masked map"
        }
        disp_objs.extend(
            make_maps_slice_montage_and_3d_display(
                in_maps=out_map, output_dir=self.output_dir
            )
        )
        # prepare a dispobj for the fsc graph
        fsc_graph = graph_from_starfile_cols(
            title="Fourier shell correlations",
            starfile=fsc_file,
            block="fsc",
            xcols=[
                "_rlnResolution",
                "_rlnResolution",
                "_rlnResolution",
            ],
            ycols=[
                "_rlnFourierShellCorrelationCorrected",
                "_rlnFourierShellCorrelationUnmaskedMaps",
                "_rlnCorrectedFourierShellCorrelationPhaseRandomizedMaskedMaps",
            ],
            data_series_labels=["Corrected", "Unmasked", "Phase randomised"],
            xlabel="1/resolution (Å<sup>−1</sup>)",
            yrange=[-0.05, 1.05],
            ylabel="Correlation",
            assoc_data=[fsc_file],
            modes=["lines"] * 3,
        )

        # add the 0.143 line to the fsc dispobj
        if isinstance(fsc_graph, ResultsDisplayGraph):
            xvals = fsc_graph.xvalues[0]
            fsc_graph.xvalues.append(xvals)
            fsc_graph.yvalues.append([0.143] * len(xvals))
            fsc_graph.modes.append("lines")
            fsc_graph.data_series_labels.append("0.143 cutoff")

        disp_objs.append(fsc_graph)
        return disp_objs

