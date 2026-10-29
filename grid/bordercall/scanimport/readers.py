"""Raw images in, with what their headers say: a CT volume (a NIfTI file, a folder holding one DICOM
series, or one DICOM file, a slice or an Enhanced CT Image) or a projection (one DICOM radiograph,
or a PNG, JPEG, TIFF or BMP).

The mask-free mode (intensity.py) measures from intensities alone, so what it is handed must be
calibrated: a CT in Hounsfield units on a grid placed in millimetres, a radiograph with the
length of its pixel at the patient where the header can say it. Every value read here carries
where it came from, and every value the header cannot give is left out, never guessed. The rules
are the DICOM standard's, as research_notes/Vertebra measures without masks/
dicom_nifti_attributes.md reads them (edition 2026c):

- CT. Output = Rescale Slope x stored value + Rescale Intercept, slice by slice, and in a CT Image
  whose Image Type Value 1 is ORIGINAL and Value 3 is not LOCALIZER, with Multi-energy CT
  Acquisition (0018,9361) absent or NO, the output "shall be" HU (PS3.3 C.8.2, Table C.8-3).
  Rescale Type (0028,1054) is required in any CT Image exactly when the output is not HU or the
  acquisition is multi-energy, so a slice whose Rescale Type is anything but HU (MGML, Z_EFF,
  HU_MOD and the other terms of PS3.3 C.11.1.1.2), or a multi-energy slice whose Rescale Type is
  not HU, is refused, and a slice with no Rescale Type is, in a conformant file, HU, ORIGINAL or
  DERIVED (a non-conformant one is left to `hu_problems`, which looks for air). An Enhanced CT
  Image keeps Rescale Type in each frame's Pixel Value Transformation (PS3.3 C.8.15.3.10), held to
  the same test. The grid comes from Image Position (Patient), Image Orientation (Patient) and
  Pixel Spacing (PS3.3 C.7.6.2.1.1, equation C.7.6.2.1-1). Slices are sorted by their position
  along the slice normal, never by Instance Number or Slice Location, and the step is the
  positions' own: Slice Thickness is nominal and Spacing Between Slices is optional and sometimes
  misused. A tilted gantry shows as slice positions off the normal; the affine takes the
  first-to-last offset as its third column, so the shear is carried exactly, not corrected.
- Projections (PS3.3 10.7.1.1 and 10.7.1.2). Imager Pixel Spacing (0018,1164) is at the front of
  the detector and never corrected for magnification; on scanned film, Nominal Scanned Pixel
  Spacing (0018,2010) is on the film (PS3.3 C.8.6.2), itself at the film's magnification, and
  stands in for it. Pixel Spacing (0028,0030) is "in the Patient": where it differs from either
  the image was corrected (Pixel Spacing Calibration Type GEOMETRY, valid at an unspecified depth)
  or calibrated against a fiducial (FIDUCIAL, valid at the fiducial's depth near the central ray);
  with no Calibration Type the method is not said. Estimated Radiographic Magnification Factor
  (0018,1114) is SID/SOD, and in DX the SOD runs to the table or bucky, not to the spine, so
  dividing by it under-corrects a vertebra that lies above the table. The scale is chosen in the
  order of the note's decision rule, the report's rows D2 to D8 (where no magnification is stated,
  the default below, midway between row D7's cervical and lumbar figures, stands in for them), and
  the spread its log carries says how far it can be trusted (`projection_scale`); a caller's pixel
  length replaces only the header's pixel length, never its magnification. Two parts of those rows
  are not followed, each said where it applies: row D6 reads SOD by module (DX to the table, CR to
  the field's centre, XA and RF to the isocentre) and adds an object depth (Clunie's M = SID / (SOD
  - depth)), and neither is built, so SID/SOD is used as the header states it, with one spread for
  every module (`stated_magnification`); and a Pixel Spacing whose provenance row D8 calls
  undeterminable is divided here by the default magnification as if it were the detector's, this
  module's choice, not D8's (`projection_scale`). A spacing is a pair, row spacing then column
  spacing (PS3.3 10.7.1.3); pixels that are not square are refused, since every chord downstream is
  scaled by one length per pixel.
- NIfTI keeps the grid, the affine and one linear scaling, and nothing of the patient. A
  dcm2niix sidecar (the same name with .json) is read for what it holds; by default dcm2niix
  leaves the patient's sex, age, size and weight out of it. NIfTI's world is RAS+ and DICOM's is
  LPS+: every affine here is RAS+, nibabel's convention. A file whose qform_code and sform_code
  are both 0 has "no particular spatial orientation" (nifti1.h, method 1), so it is refused rather
  than read through nibabel's fall-back affine, which would guess which way is up and which is
  in front.
- PNG and JPEG carry no length at the patient. A pHYs chunk, a JFIF density or an EXIF
  resolution describes print or display size, and exporters write defaults, so none of them ever
  sets a scale here. A caller who knows the pixel's length gives it.

A projection is read for its header and its size as shown, never its pixels, since nothing
downstream reads a projection's intensities (film.py measures from what was drawn on the image):
decoding them would only refuse an image for what does not change its column, a compressed
transfer syntax pydicom has no decoder for, or a palette. `read_projection(..., with_pixels=True)`
decodes them, grey with bone bright, for a caller that needs them.

pydicom (MIT) reads DICOM and Pillow reads PNG and JPEG; both are imported only when such a file
is read, so the rest of the package needs neither.
"""
from __future__ import annotations

import json
import math
import os
from collections import abc
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .column import sha256_of           # the package's one digest, of an image file as of any input

# SOP Class UIDs, the first thing a lone file is classified by, as the research note takes them from
# pydicom's UID dictionary (dicom_nifti_attributes.md; the report's step R0).
CT_IMAGE = "1.2.840.10008.5.1.4.1.1.2"
ENHANCED_CT = "1.2.840.10008.5.1.4.1.1.2.1"
ENHANCED_SOURCE = "dicom-enhanced-ct"   # a volume's source when it was one Enhanced CT Image's frames
PROJECTION_CLASSES = {
    "1.2.840.10008.5.1.4.1.1.1": "CR",
    "1.2.840.10008.5.1.4.1.1.1.1": "DX for presentation",
    "1.2.840.10008.5.1.4.1.1.1.1.1": "DX for processing",
    "1.2.840.10008.5.1.4.1.1.12.1": "XA",
    "1.2.840.10008.5.1.4.1.1.12.2": "XRF",
}
# The secondary capture family by exact UID, as the report's step R0 lists it (.7 and .7.1 to .7.4);
# a prefix would also take the VL classes .77.x and the ophthalmic .78.x and .79.x.
SECONDARY_CAPTURE = {
    "1.2.840.10008.5.1.4.1.1.7": "secondary capture",
    "1.2.840.10008.5.1.4.1.1.7.1": "multi-frame single bit secondary capture",
    "1.2.840.10008.5.1.4.1.1.7.2": "multi-frame grayscale byte secondary capture",
    "1.2.840.10008.5.1.4.1.1.7.3": "multi-frame grayscale word secondary capture",
    "1.2.840.10008.5.1.4.1.1.7.4": "multi-frame true color secondary capture",
}

# The acquisition attributes an Enhanced CT Image keeps in a functional group macro, not at the
# top level (the note, on PS3.3 C.8.15): the attribute, the macro's sequence and its name.
ENHANCED_CT_MACROS = {
    "KVP": ("CTXRayDetailsSequence", "CT X-Ray Details (0018,9325)"),
    "ConvolutionKernel": ("CTReconstructionSequence", "CT Reconstruction (0018,9314)"),
    "SliceThickness": ("PixelMeasuresSequence", "Pixel Measures (0028,9110)"),
}

# The tolerances a series is held to: a direction cosine differing by more than this between
# slices, or slice steps differing by more than this share of their median, is refused.
ORIENTATION_TOLERANCE = 1e-4
STEP_TOLERANCE = 0.01
LPS_TO_RAS = np.diag([-1.0, -1.0, 1.0, 1.0])

# Patient's Size is in metres (PS3.3 C.7.2.2); a value above this is probably centimetres, as the
# note's inference and the report's row D10 say (an inference: no source counted such errors).
MOST_METRES = 3.0

# A film's magnification where the header gives nothing better, the one default of the package
# (radiograph.py takes it from here). The report's row D7 rests on Ravi B, Rampersaud YR, Orthop
# Procs 2009;91-B(SUPP_II):251-252 (masks_corners_magnification.md, section 4): against CT or MRI,
# vertebral bodies on lateral digital films were magnified 1.21 at the cervical spine (range 1.06
# to 1.57) and 1.31 at the lumbar spine (range 1.09 to 1.63), rising with BMI, more than the nominal
# 1.1 to 1.2 the note says real films exceed. The default, 1.26, is the midpoint of the two means;
# its log spread, 0.10, puts the published extremes 1.7 spreads below it (ln(1.26/1.06) = 0.17) and
# 2.6 above it (ln(1.63/1.26) = 0.26), so the range lies within about two spreads, its lumbar top a
# little beyond. Both are this module's choices, not the paper's; it measured lateral films only and
# the report found no AP figure, so an AP film takes the same default.
DEFAULT_MAGNIFICATION, DEFAULT_MAGNIFICATION_LOG_SD = 1.26, 0.10

# The spread of log magnification each other kind of scale carries: this module's stated choices,
# since no source read measures them. A fiducial is measured in the image, near the central ray at
# its own depth, so it is trusted most. A geometric correction holds at an unspecified depth (PS3.3
# 10.7.1.2) and a stated factor at the point SOD runs to, in DX the table or bucky (PS3.3
# C.8.11.5), neither the vertebra's own depth; a correction whose kind the header does not say
# carries the same spread, the wider of the two kinds the standard names. A stated SID/SOD carries
# it whatever the module: the report's row D6 reads SOD by module (DX the table, CR the field's
# centre, XA the isocentre) and adds an object depth (Clunie), and neither is built here, so this
# one spread stands for all of them. A Pixel Spacing with nothing to say whether it was corrected
# (PS3.3 10.7.1.1) is trusted least. Treating it as the detector's pixel and dividing it by the
# default magnification is this module's choice (projection_scale), not row D8's, which says only
# that its provenance cannot be determined: had it been corrected already, its chords are about
# 21 per cent short (1 - 1/1.26), and magnification 1 lies 1.9 of this spread below the default
# (ln 1.26 / 0.12).
FIDUCIAL_LOG_SD, STATED_LOG_SD, UNKNOWN_PROVENANCE_LOG_SD = 0.03, 0.05, 0.12

# Two spacings within this share of each other are taken as one value written to different
# precision: a pixel's row and column spacing, or a Pixel Spacing and an Imager Pixel Spacing.
# This module's own choice: averaging a pair this close moves a chord by about half a per cent at
# most, and the smallest magnification the report's prior art gives for a spine film, 1.06 (its row
# D7, Ravi and Rampersaud 2009), lies six times further out, so no correction hides inside it.
SPACING_AGREEMENT = 0.01

# The luma weights Pillow documents for convert("L") (its documentation names them ITU-R 601-2 luma;
# no research note covers them), which read_picture applies, so a colour DICOM is made grey as a
# colour picture is.
LUMA = np.array([0.299, 0.587, 0.114])

# A series whose slices step off their normal by more than this share of the step is said to come
# from a tilted gantry. This module's choice: one part in a thousand is 0.003 mm on a 3 mm step,
# far below any voxel, so only a real tilt passes it, and the positions' own rounding (written to
# a few decimals) does not.
TILT_SHARE = 1e-3

# The bounds a caller's own numbers are held to, as the header's are (caller_value): a pixel is a
# length above 0; a magnification is at least 1, since no object between the source and the
# detector is shown smaller than it is (1 itself is a pixel the caller already gives at the
# patient, as a DRR rendered at its object's plane may be); a spread of log magnification is 0 or
# more.
LEAST_PIXEL_MM, LEAST_MAGNIFICATION, LEAST_LOG_SD = 0.0, 1.0, 0.0


@dataclass
class Volume:
    """A CT in HU on a grid placed in millimetres: hu[i, j, k], affine from (i, j, k, 1) to RAS+
    millimetres."""
    hu: np.ndarray
    affine: np.ndarray
    source: str
    header: Dict[str, dict] = field(default_factory=dict)
    problems: List[str] = field(default_factory=list)

    @property
    def spacing(self) -> np.ndarray:
        return np.linalg.norm(self.affine[:3, :3], axis=0)


@dataclass
class Projection:
    """One projection image as shown: its size (rows, columns, after any EXIF turn), its scale and,
    where they were asked for (read_projection's with_pixels), pixels[row, column] in one channel,
    with bone bright where the file says which way its contrast runs (a DICOM file's photometric
    interpretation) and as stored where it does not (a picture file)."""
    size: Tuple[int, int]
    sha256: str
    source: str
    scale: dict
    header: Dict[str, dict] = field(default_factory=dict)
    problems: List[str] = field(default_factory=list)
    pixels: Optional[np.ndarray] = None

    @property
    def height(self) -> int:
        return int(self.size[0])

    @property
    def width(self) -> int:
        return int(self.size[1])


def noted(value, source: str) -> dict:
    return {"value": value, "from": source}


# ---- the patient and the acquisition ---------------------------------------------------------------

PLACEHOLDER_AGE = "000Y"


def age_in_years(age: str) -> Optional[float]:
    """A DICOM Age String (PS3.5 6.2, AS: nnnD, nnnW, nnnM or nnnY) in years; None if malformed,
    or if it is 000Y, which is treated as missing, as the note's inference says. The note gives no
    reason; the one here, that an age under a year is written in D, W or M, so zero years says
    nothing, is this module's."""
    age = (age or "").strip()
    if len(age) != 4 or not age[:3].isdigit() or age[3] not in "DWMY" or age == PLACEHOLDER_AGE:
        return None
    per_year = {"D": 365.25, "W": 365.25 / 7.0, "M": 12.0, "Y": 1.0}[age[3]]
    return round(int(age[:3]) / per_year, 3)


def age_noted(raw, source: str) -> Optional[dict]:
    """An age in years with where it came from; 000Y is kept as a value left out, with why, so the
    record shows it was there; any other string that is not an Age String is left out."""
    text = str(raw or "").strip()
    if text == PLACEHOLDER_AGE:
        return noted(None, "%s %s: zero years, treated as missing, as the note's inference says; the reason, that an "
                           "age under a year is written in D, W or M (PS3.5 6.2), is this module's" % (source, text))
    age = age_in_years(text)
    return None if age is None else noted(age, source)


def height_noted(metres, source: str) -> Optional[dict]:
    """Patient's Size, in metres in the header (PS3.3 C.7.2.2), as centimetres; a value above
    MOST_METRES is probably centimetres already and is left out, with why, rather than recorded as
    a patient a hundred times too tall."""
    if metres in (None, "") or float(metres) <= 0:
        return None
    if float(metres) > MOST_METRES:
        return noted(None, "%s %s: above %.0f, so probably centimetres, not the metres the standard says; left out"
                     % (source, metres, MOST_METRES))
    return noted(round(float(metres) * 100.0, 3), source)


def acquisition_value(ds, attr: str) -> Tuple[object, str]:
    """An acquisition attribute and where it sits: in an Enhanced CT Image, KVP, Convolution
    Kernel and Slice Thickness are in functional group macros (ENHANCED_CT_MACROS), read for the
    first frame; elsewhere, and where the macro lacks it, at the top level."""
    if str(getattr(ds, "SOPClassUID", "")) == ENHANCED_CT and attr in ENHANCED_CT_MACROS:
        sequence, macro = ENHANCED_CT_MACROS[attr]
        item = group_item(ds, 0, sequence)
        v = getattr(item, attr, None) if item is not None else None
        if v not in (None, ""):
            return v, " in %s, frame 1" % macro
    return getattr(ds, attr, None), ""


def dicom_covariates(ds) -> Dict[str, dict]:
    """The patient's sex, age, height and weight and the acquisition's settings, where the file
    holds them. Sex and Birth Date are type 2 (present, may be empty); Age, Size and Weight are
    type 3 and removed by the PS3.15 Basic Profile unless its Retain Patient Characteristics
    Option was applied, so their absence says nothing about the patient."""
    out: Dict[str, dict] = {}
    sex = str(getattr(ds, "PatientSex", "") or "").strip().upper()
    if sex in ("M", "F", "O"):
        out["sex"] = noted(sex, "PatientSex (0010,0040)")
    found = {"age_years": age_noted(getattr(ds, "PatientAge", None), "PatientAge (0010,1010)"),
             "height_cm": height_noted(getattr(ds, "PatientSize", None), "PatientSize (0010,1020)")}
    weight = getattr(ds, "PatientWeight", None)
    if weight not in (None, "") and float(weight) > 0:
        found["weight_kg"] = noted(round(float(weight), 3), "PatientWeight (0010,1030)")
    out.update({k: v for k, v in found.items() if v is not None})
    for key, attr, tag in (("manufacturer", "Manufacturer", "(0008,0070)"), ("model", "ManufacturerModelName", "(0008,1090)"),
                           ("kvp", "KVP", "(0018,0060)"), ("kernel", "ConvolutionKernel", "(0018,1210)"),
                           ("slice_thickness_mm", "SliceThickness", "(0018,0050)"),
                           ("patient_position", "PatientPosition", "(0018,5100)"),
                           ("view_position", "ViewPosition", "(0018,5101)"),
                           ("body_part", "BodyPartExamined", "(0018,0015)")):
        v, where = acquisition_value(ds, attr)
        if v not in (None, ""):
            out[key] = noted(v if isinstance(v, (int, float, str)) else str(v), "%s %s%s" % (attr, tag, where))
    return out


SIDECAR_KEYS = {"PatientSex": "sex", "PatientAge": "age_years", "PatientSize": "height_cm",
                "PatientWeight": "weight_kg", "Manufacturer": "manufacturer",
                "ManufacturersModelName": "model", "ConvolutionKernel": "kernel",
                "SliceThickness": "slice_thickness_mm", "PatientPosition": "patient_position"}


def sidecar_path(nifti_path: str) -> str:
    """Where dcm2niix writes a NIfTI's BIDS sidecar: the same name with .json in place of .nii.gz or
    .nii, the extension matched in either case as read_volume matches it. The one rule for the
    reader and for the command line, which hashes the sidecar as an input."""
    if nifti_path.lower().endswith(".nii.gz"):
        return nifti_path[:-7] + ".json"
    return os.path.splitext(nifti_path)[0] + ".json"


def sidecar_covariates(nifti_path: str) -> Dict[str, dict]:
    """What a dcm2niix BIDS sidecar beside a NIfTI holds of the same covariates."""
    path = sidecar_path(nifti_path)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        side = json.load(fh)
    out: Dict[str, dict] = {}
    for key, name in SIDECAR_KEYS.items():
        if key not in side or side[key] in (None, ""):
            continue
        v, source = side[key], "dcm2niix sidecar %s" % key
        if name == "height_cm":
            entry = height_noted(v, source)
        elif name == "age_years":
            entry = age_noted(v, source) if isinstance(v, str) else noted(float(v), source)
        else:
            entry = noted(v, source)
        if entry is not None:
            out[name] = entry
    return out


# ---- CT volumes ---------------------------------------------------------------------------------------

def read_volume(path: str, series_uid: Optional[str] = None) -> Volume:
    """A CT from a NIfTI file, a folder of one DICOM series, or one DICOM file. A Series Instance
    UID, where the caller names one, is held to what is read: it picks the series in a folder, a
    lone DICOM file must belong to it, and a NIfTI file, which keeps no Series Instance UID, is
    refused with it rather than read as if none had been named."""
    if os.path.isdir(path):
        return read_dicom_series(path, series_uid)
    low = path.lower()
    if low.endswith(".nii") or low.endswith(".nii.gz"):
        if series_uid is not None:
            raise SystemExit("--series %s names a DICOM series, but %s is a NIfTI file, which keeps no Series Instance "
                             "UID to hold it to; leave --series out, or give the DICOM folder" % (series_uid, path))
        return read_nifti(path)
    return read_dicom_series_files([path], "dicom-slice", series_uid)


def read_nifti(path: str) -> Volume:
    """A CT from a NIfTI file, through the affine its header codes as meaningful. A fourth and
    later dimension of length 1, which some converters write for one volume, is dropped."""
    import nibabel as nib
    img = nib.load(path)
    if int(img.get_sform(coded=True)[1]) == 0 and int(img.get_qform(coded=True)[1]) == 0:
        raise SystemExit("%s has qform_code and sform_code both 0, so its orientation is unknown (nifti1.h, method 1); "
                         "the mask-free mode needs to know which way is up and which is in front, so give it the "
                         "file's orientation first, or convert the DICOM again with dcm2niix" % path)
    hu = np.asarray(img.get_fdata(dtype=np.float32))
    if hu.ndim > 3 and all(n == 1 for n in hu.shape[3:]):
        hu = hu.reshape(hu.shape[:3])
    if hu.ndim != 3:
        raise SystemExit("%s holds an image of shape %s; a CT volume has three dimensions"
                         % (path, " x ".join(str(n) for n in hu.shape)))
    vol = Volume(hu=hu, affine=np.asarray(img.affine, float), source="nifti", header=sidecar_covariates(path))
    vol.problems += hu_problems(hu)
    return vol


def hu_problems(hu: np.ndarray) -> List[str]:
    """In words, why the intensities may not be HU: air outside the patient lies near -1000 HU, so
    a volume whose lowest percentile is far above that was stored uncalibrated."""
    low = float(np.percentile(hu, 1))
    if low > -500.0:
        return ["the lowest 1 per cent of voxels is %.0f, far above air's -1000 HU; the volume may not be "
                "in HU, and no threshold here would mean what it says" % low]
    return []


def read_dicom_series(folder: str, series_uid: Optional[str] = None) -> Volume:
    files = sorted(os.path.join(r, f) for r, _, fs in os.walk(folder) for f in fs)
    return read_dicom_series_files(files, "dicom-series", series_uid)


def read_dicom_series_files(files: Sequence[str], source: str, series_uid: Optional[str] = None) -> Volume:
    """One CT from DICOM files: the slices of one series of CT Images, or one Enhanced CT Image,
    which holds a whole volume as frames in one file. Localizers are left out, since a scout is
    a projection; other files a folder holds are passed over. The volume's source says what was
    read: ENHANCED_SOURCE for an Enhanced CT Image, else `source` (dicom-series for a folder,
    dicom-slice for one file)."""
    import pydicom
    from pydicom.errors import InvalidDicomError
    slices, enhanced = [], []
    for f in files:
        try:
            ds = pydicom.dcmread(f)
        except (InvalidDicomError, IsADirectoryError):
            continue                                   # not a DICOM file: a folder may hold others
        sop = str(getattr(ds, "SOPClassUID", ""))
        if sop == ENHANCED_CT:
            enhanced.append(ds)
        elif sop == CT_IMAGE and not is_localizer(ds):
            slices.append(ds)
    found = slices + enhanced
    if not found:
        raise SystemExit("no CT Image slice (SOP class %s, not a localizer) and no Enhanced CT Image (%s) among %d files"
                         % (CT_IMAGE, ENHANCED_CT, len(files)))
    uids = sorted({str(ds.SeriesInstanceUID) for ds in found})
    if series_uid is not None:
        found = [ds for ds in found if str(ds.SeriesInstanceUID) == series_uid]
        if not found:
            raise SystemExit("no CT series %s among the files; they hold %s" % (series_uid, ", ".join(uids)))
    elif len(uids) > 1:
        raise SystemExit("the files hold %d CT series (%s); name one with --series" % (len(uids), ", ".join(uids)))
    if any(str(ds.SOPClassUID) == ENHANCED_CT for ds in found):
        if len(found) > 1:
            raise SystemExit("the series holds %d files with an Enhanced CT Image among them; one Enhanced CT Image "
                             "holds the whole volume" % len(found))
        frames = enhanced_frames(found[0])
        return stack_planes(frames, ENHANCED_SOURCE, dicom_covariates(found[0]), "an Enhanced CT Image's frames")
    return stack_planes([plane_of(ds) for ds in found], source, dicom_covariates(found[0]), "the files")


def is_localizer(ds) -> bool:
    """A CT localizer, by Image Type's third value (PS3.3 C.8.2.1.1.1)."""
    kinds = [str(x).upper() for x in getattr(ds, "ImageType", [])]
    return len(kinds) > 2 and kinds[2] == "LOCALIZER"


@dataclass
class Plane:
    """One CT slice, from a CT Image or one frame of an Enhanced CT Image: its row direction
    (along increasing column index) and column direction in LPS, the position of its first
    pixel in LPS millimetres, its spacing (between rows, between columns) and its HU."""
    row: np.ndarray
    col: np.ndarray
    position: np.ndarray
    spacing: Tuple[float, float]
    hu: np.ndarray
    thickness: Optional[float] = None


def pixels_of(ds) -> np.ndarray:
    """The stored values, or a refusal naming the transfer syntax pydicom could not decode."""
    try:
        return ds.pixel_array
    except Exception as err:                        # pydicom raises several kinds for a missing decoder
        syntax = getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", "unknown")
        raise SystemExit("the pixel data could not be decoded (transfer syntax %s: %s); decompress the files first, "
                         "for example with dcmdjpeg or gdcmconv --raw" % (syntax, err))


def rescaled(stored: np.ndarray, slope, intercept) -> np.ndarray:
    """Output = Rescale Slope x stored value + Rescale Intercept (PS3.3 C.8.2, Table C.8-3); HU
    for a CT slice that `not_hu` passes."""
    s = float(slope) if slope not in (None, "") else 1.0
    i = float(intercept) if intercept not in (None, "") else 0.0
    return stored.astype(np.float64) * s + i


def not_hu(rescale_type, multi_energy) -> Optional[str]:
    """Why a CT slice's rescaled values are not Hounsfield units, or None where they are. Rescale
    Type is required whenever the output is not HU or Multi-energy CT Acquisition is YES (PS3.3
    C.8.2), so a Rescale Type other than HU says the values are something else, a multi-energy
    slice must say HU to be HU, and a slice with neither is HU, whatever its Image Type."""
    kind = str(rescale_type or "").strip().upper()
    if kind and kind != "HU":
        return "Rescale Type (0028,1054) is %s, not HU" % kind
    if str(multi_energy or "").strip().upper() == "YES" and kind != "HU":
        return "a multi-energy acquisition (0018,9361 YES) whose Rescale Type is not HU"
    return None


def refuse_unless_hu(rescale_type, multi_energy, which: str) -> None:
    reason = not_hu(rescale_type, multi_energy)
    if reason:
        raise SystemExit("%s: %s, so its values are not Hounsfield units (PS3.3 C.8.2), and every threshold of the "
                         "mask-free mode is in HU" % (which, reason))


def plane_of(ds) -> Plane:
    refuse_unless_hu(getattr(ds, "RescaleType", None), getattr(ds, "MultienergyCTAcquisition", None),
                     "the CT slice %s" % getattr(ds, "SOPInstanceUID", "with no SOP Instance UID"))
    iop = np.asarray([float(v) for v in ds.ImageOrientationPatient])
    ipp = np.asarray([float(v) for v in ds.ImagePositionPatient])
    dr, dc = (float(v) for v in ds.PixelSpacing)
    hu = rescaled(pixels_of(ds), getattr(ds, "RescaleSlope", None), getattr(ds, "RescaleIntercept", None))
    thick = getattr(ds, "SliceThickness", None)
    return Plane(iop[:3], iop[3:], ipp, (dr, dc), hu, float(thick) if thick not in (None, "") else None)


def group_item(ds, i: int, name: str):
    """The first item of functional group macro `name` for frame i: the frame's own, else the
    shared one (PS3.3 C.7.6.16.1.1 and C.7.6.16.1.2: a macro is in one of the two sequences, never
    both)."""
    for seq in ("PerFrameFunctionalGroupsSequence", "SharedFunctionalGroupsSequence"):
        groups = getattr(ds, seq, None)
        if not groups:
            continue
        item = groups[i] if seq.startswith("PerFrame") else groups[0]
        inner = getattr(item, name, None)
        if inner:
            return inner[0]
    return None


def enhanced_frames(ds) -> List[Plane]:
    """The frames of an Enhanced CT Image as planes, each read from its functional groups: Plane
    Position, Plane Orientation and Pixel Measures macros (PS3.3 C.7.6.16.2) and the CT Pixel Value
    Transformation macro (PS3.3 C.8.15.3.10), whose Rescale Type is held to `not_hu` frame by frame.
    Localizer frames (Frame Type's third value) are left out."""
    stored = pixels_of(ds)
    n = int(getattr(ds, "NumberOfFrames", 1) or 1)
    stored = stored.reshape((n,) + stored.shape[-2:])
    out = []
    for i in range(n):
        kind = group_item(ds, i, "CTImageFrameTypeSequence")
        kinds = [str(x).upper() for x in getattr(kind, "FrameType", [])] if kind is not None else []
        if len(kinds) > 2 and kinds[2] == "LOCALIZER":
            continue
        pos, ori = group_item(ds, i, "PlanePositionSequence"), group_item(ds, i, "PlaneOrientationSequence")
        meas, rescale = group_item(ds, i, "PixelMeasuresSequence"), group_item(ds, i, "PixelValueTransformationSequence")
        if pos is None or ori is None or meas is None:
            raise SystemExit("frame %d of the Enhanced CT Image has no plane position, orientation or pixel measures" % (i + 1))
        refuse_unless_hu(getattr(rescale, "RescaleType", None), getattr(ds, "MultienergyCTAcquisition", None),
                         "frame %d of the Enhanced CT Image" % (i + 1))
        iop = np.asarray([float(v) for v in ori.ImageOrientationPatient])
        dr, dc = (float(v) for v in meas.PixelSpacing)
        thick = getattr(meas, "SliceThickness", None)
        hu = rescaled(stored[i], getattr(rescale, "RescaleSlope", None), getattr(rescale, "RescaleIntercept", None))
        out.append(Plane(iop[:3], iop[3:], np.asarray([float(v) for v in pos.ImagePositionPatient]), (dr, dc), hu,
                         float(thick) if thick not in (None, "") else None))
    if not out:
        raise SystemExit("the Enhanced CT Image holds only localizer frames")
    return out


def stack_planes(planes: List[Plane], source: str, header: Dict[str, dict], counted_from: str) -> Volume:
    """One volume from slices of one orientation and one step, sorted by their position along
    the slice normal (never by Instance Number or Slice Location)."""
    row0, col0 = planes[0].row, planes[0].col
    problems = []
    for p in planes[1:]:
        if np.abs(p.row - row0).max() > ORIENTATION_TOLERANCE or np.abs(p.col - col0).max() > ORIENTATION_TOLERANCE:
            raise SystemExit("the slices do not share one orientation; a series of one acquisition does")
        if p.hu.shape != planes[0].hu.shape or np.abs(np.subtract(p.spacing, planes[0].spacing)).max() > 1e-6:
            raise SystemExit("the slices do not share one size and pixel spacing; a volume needs one grid")
    normal = np.cross(row0, col0)
    planes = sorted(planes, key=lambda p: float(np.dot(normal, p.position)))
    depth = np.array([float(np.dot(normal, p.position)) for p in planes])
    if len(planes) > 1:
        steps = np.diff(depth)
        median = float(np.median(steps))
        if median <= 0 or np.abs(steps - median).max() > STEP_TOLERANCE * median:
            raise SystemExit("the slice steps run from %.3f to %.3f mm; a volume needs one step (a slice missing, "
                             "or two series mixed)" % (steps.min(), steps.max()))
    dr, dc = planes[0].spacing
    first = planes[0].position
    if len(planes) > 1:
        third = (planes[-1].position - first) / (len(planes) - 1)
        off_normal = np.linalg.norm(third - np.dot(third, normal) * normal)
        if off_normal > TILT_SHARE * np.linalg.norm(third):
            problems.append("the slices step %.3f mm off their normal (a tilted gantry); the grid carries the shear"
                            % off_normal)
    else:
        third = normal * (planes[0].thickness or 1.0)
        problems.append("one slice: the through-plane step is not known, so the volume has no third dimension to "
                        "follow the column along")
    # hu[i, j, k]: i the column index, j the row index, k the slice, so the affine's columns are
    # the row direction times the column spacing, the column direction times the row spacing, the step
    lps = np.eye(4)
    lps[:3, 0], lps[:3, 1], lps[:3, 2], lps[:3, 3] = row0 * dc, col0 * dr, third, first
    hu = np.stack([p.hu.T for p in planes], axis=2).astype(np.float32)
    vol = Volume(hu=hu, affine=LPS_TO_RAS @ lps, source=source, header=dict(header), problems=problems)
    vol.header["slices"] = noted(len(planes), counted_from)
    vol.problems += hu_problems(hu) if len(planes) > 1 else []
    return vol


# ---- projections --------------------------------------------------------------------------------------

# A picture file is known by its suffix; any other file is read as DICOM.
PICTURE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
# The EXIF orientations that turn the stored image a quarter turn (TIFF/EXIF Orientation 5 to 8,
# the ones Pillow's exif_transpose meets with a transpose or a rotation by 90 or 270 degrees), so
# the shown image's rows are the stored image's columns.
QUARTER_TURNS = (5, 6, 7, 8)


def read_projection(path: str, pixel_mm: Optional[float] = None, with_pixels: bool = False) -> Projection:
    """One radiograph or fluoroscopy frame: a DICOM file, a PNG, JPEG, TIFF or BMP. Its size as
    shown and its scale come from its header; its pixels are decoded only `with_pixels` (the
    module's docstring says why)."""
    if path.lower().endswith(PICTURE_SUFFIXES):
        return read_picture(path, pixel_mm, with_pixels)
    return read_dicom_projection(path, pixel_mm, with_pixels)


def read_picture(path: str, pixel_mm: Optional[float], with_pixels: bool = False) -> Projection:
    """A PNG, JPEG, TIFF or BMP as it is shown: an EXIF orientation is applied first, as FleXray
    applies it, so corners and masks drawn on the shown image land where they were drawn. Its size
    is the shown image's, read without decoding a pixel (Pillow opens a file lazily)."""
    from PIL import Image
    pixel_mm = caller_value(pixel_mm, "--pixel-mm", LEAST_PIXEL_MM, inclusive=False)
    header: Dict[str, dict] = {}
    with Image.open(path) as im:
        turn = im.getexif().get(0x0112, 1)
        if turn not in (None, 1):
            header["exif_orientation"] = noted(int(turn), "EXIF Orientation (0x0112), applied")
        width, height = im.size
        size = (width, height) if turn in QUARTER_TURNS else (height, width)
        mode = im.mode
        pixels = picture_pixels(im, turn) if with_pixels else None
    scale = unknown_scale("unknown: a picture file carries no length at the patient")
    if pixel_mm is not None:
        scale = scaled_at_detector(pixel_mm, "the caller's pixel size")
    return Projection(size=size, sha256=sha256_of(path), source="picture (%s)" % mode, scale=scale, header=header,
                      problems=[] if pixel_mm is not None else
                      ["no pixel size: the chords stay in pixels and the scale is unknown"], pixels=pixels)


def picture_pixels(im, turn) -> np.ndarray:
    """A picture's pixels as shown, in one channel: sixteen-bit grey as stored, anything else
    through Pillow's convert("L") (LUMA for colour). A picture file does not say which way its
    contrast runs, so they are as stored, never turned over."""
    from PIL import ImageOps
    shown = ImageOps.exif_transpose(im) if turn not in (None, 1) else im
    if shown.mode in ("I;16", "I;16B", "I;16L", "I"):
        return np.asarray(shown, dtype=np.float64)
    return np.asarray(shown.convert("L"), dtype=np.float64)


def unknown_scale(basis: str) -> dict:
    return {"pixel_mm": None, "pixel_mm_at_detector": None, "magnification": None, "log_sd": None, "basis": basis}


def scaled_at_detector(pixel_mm: float, basis: str, magnification: Optional[float] = None,
                       log_sd: Optional[float] = None, said: str = "stated") -> dict:
    """A pixel at the detector over a magnification the header gave (`said` says how: stated, or
    implied by two spacings) or, where it gave none, the default."""
    m = DEFAULT_MAGNIFICATION if magnification is None else magnification
    sd = (DEFAULT_MAGNIFICATION_LOG_SD if magnification is None else STATED_LOG_SD) if log_sd is None else log_sd
    return {"pixel_mm": pixel_mm / m, "pixel_mm_at_detector": pixel_mm, "magnification": m, "log_sd": sd,
            "basis": basis + ("; magnification %.3f %s" % (m, said) if magnification is not None
                              else "; the default magnification %.2f, log spread %.2f" % (m, sd))}


def at_patient(pixel_mm: float, detector: Optional[float], log_sd: float, basis: str) -> dict:
    """A pixel the header gives at the patient. Where it gives the unmagnified pixel too (the
    detector's or the scanned film's, `Unmagnified`), the magnification is their ratio, so in every
    scale here pixel_mm x magnification is that pixel; where it does not, the pixel is taken as it
    is, at magnification 1."""
    return {"pixel_mm": pixel_mm, "pixel_mm_at_detector": detector,
            "magnification": detector / pixel_mm if detector else 1.0, "log_sd": log_sd, "basis": basis}


def spacing_of(ds, keyword: str, tag: str, problems: List[str]) -> Optional[float]:
    """One pixel length from a spacing attribute, a pair of row spacing then column spacing (PS3.3
    10.7.1.3), or None where it is absent, or is not a pair of positive lengths (then left out, and
    said so). Pixels that are not square are refused: every chord downstream is scaled by one
    length per pixel (radiograph.ingest_docs), so one along the rows and one along the columns
    would be wrong in opposite directions."""
    raw = getattr(ds, keyword, None)
    if raw is None or isinstance(raw, (str, bytes)) and not raw.strip():
        return None
    values = [float(v) for v in raw] if isinstance(raw, abc.Sequence) and not isinstance(raw, str) else [float(raw)]
    if not values:
        return None
    if len(values) != 2 or min(values) <= 0:
        problems.append("%s %s is %s, not a pair of positive row and column spacings (PS3.3 10.7.1.3); it is left out"
                        % (keyword, tag, "\\".join("%g" % v for v in values)))
        return None
    row, column = values
    if abs(row - column) > SPACING_AGREEMENT * max(row, column):
        raise SystemExit("%s %s gives a row spacing of %.4f mm and a column spacing of %.4f mm: the pixels are not "
                         "square, and every chord here is scaled by one length per pixel, so resample the image, with "
                         "what was drawn on it, to square pixels first" % (keyword, tag, row, column))
    return (row + column) / 2.0


def caller_value(value, what: str, least: float, inclusive: bool) -> Optional[float]:
    """A number the caller gives in place of the header's (a pixel length, a magnification or its
    spread), or None where none is given. It is held to the same bounds a header's value is: a value
    that is not a finite number, or that lies below `least` (or at it, where `inclusive` is False),
    is refused, since read on it would set every chord with the scale still called known; and 0 is
    refused like any other value out of bounds, never skipped as if nothing had been given."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = math.nan
    if not math.isfinite(number) or number < least or (number == least and not inclusive):
        raise SystemExit("%s is %r; it must be a finite number %s %g" % (what, value, "of at least" if inclusive
                                                                         else "above", least))
    return number


def same_length(a: float, b: float) -> bool:
    return abs(a - b) <= SPACING_AGREEMENT * max(a, b)


@dataclass
class Unmagnified:
    """The pixel's length where the image was formed, before any correction for magnification:
    Imager Pixel Spacing at the front of the detector, or, for scanned film, Nominal Scanned Pixel
    Spacing on the film (PS3.3 C.8.6.2), itself at the film's magnification, as the note reads it.
    PS3.3 10.7.1.1 holds Pixel Spacing against either."""
    length: float
    name: str
    plane: str


def unmagnified_spacing(ds, problems: List[str]) -> Optional[Unmagnified]:
    """Imager Pixel Spacing where the header gives it, else Nominal Scanned Pixel Spacing, else None."""
    ips = spacing_of(ds, "ImagerPixelSpacing", "(0018,1164)", problems)
    if ips is not None:
        return Unmagnified(ips, "Imager Pixel Spacing (0018,1164)", "at the detector")
    nsps = spacing_of(ds, "NominalScannedPixelSpacing", "(0018,2010)", problems)
    if nsps is not None:
        return Unmagnified(nsps, "Nominal Scanned Pixel Spacing (0018,2010)", "on the scanned film")
    return None


def calibrated(ps: float, kind: str, raw: Optional[Unmagnified], log_sd: float, basis: str,
               problems: List[str]) -> dict:
    """A Pixel Spacing calibrated or corrected by a stated kind (rows D2 and D3), used as it is. One
    larger than the unmagnified pixel would put the patient at a magnification below 1, which no
    object between the source and the detector has; the header then contradicts itself, and that is
    recorded beside the calibrated value."""
    if raw is not None and ps > raw.length and not same_length(ps, raw.length):
        problems.append("Pixel Spacing %.4f mm, of calibration type %s, is larger than %s %.4f mm, which puts the "
                        "patient at a magnification below 1; the header contradicts itself, and the calibrated Pixel "
                        "Spacing is used" % (ps, kind, raw.name, raw.length))
    return at_patient(ps, raw.length if raw is not None else None, log_sd, basis)


def corrected_spacing(ds, ps: Optional[float], raw: Optional[Unmagnified], problems: List[str]) -> Optional[dict]:
    """Pixel Spacing the header gives at the patient, the report's rows D2 to D4: calibrated against
    a fiducial, corrected for geometry, or, with no Calibration Type, smaller than the unmagnified
    pixel (Imager or Nominal Scanned Pixel Spacing), which PS3.3 10.7.1.1 reads as corrected or
    calibrated by a method the header does not say. None where Pixel Spacing is no such value. A
    Pixel Spacing larger than the unmagnified pixel with no Calibration Type contradicts the
    geometry, since a correction for magnification only makes the pixel smaller; it is recorded as
    a problem and passed over."""
    if ps is None:
        return None
    kind = str(getattr(ds, "PixelSpacingCalibrationType", "") or "").strip().upper()
    if kind == "FIDUCIAL":
        return calibrated(ps, kind, raw, FIDUCIAL_LOG_SD,
                          "Pixel Spacing calibrated against a fiducial (0028,0A02 FIDUCIAL)", problems)
    if kind == "GEOMETRY":
        return calibrated(ps, kind, raw, STATED_LOG_SD,
                          "Pixel Spacing corrected for geometric magnification (0028,0A02 GEOMETRY)", problems)
    if raw is None or same_length(ps, raw.length):
        return None
    if ps < raw.length:
        return at_patient(ps, raw.length, STATED_LOG_SD,
                          "Pixel Spacing (0028,0030) smaller than %s with no calibration type: corrected for "
                          "magnification or calibrated against an object, by a method not stated (PS3.3 10.7.1.1)"
                          % raw.name)
    problems.append("Pixel Spacing %.4f mm is larger than %s %.4f mm with no calibration type; a correction for "
                    "magnification only makes the pixel smaller, so the header contradicts itself and %s is used"
                    % (ps, raw.name, raw.length, raw.name))
    return None


def stated_magnification(ds, problems: List[str]) -> Optional[Tuple[float, float, str]]:
    """The magnification the header states, its spread and where it came from: the Estimated
    Radiographic Magnification Factor where it is above 1 (the report's row D5, as Cornerstone3D
    reads it), else SID/SOD where the source-to-patient distance is the shorter (row D6); None
    where it states neither. D6 is followed only in part: it reads SOD by module (DX to the table,
    CR to the field's centre, XA and RF to the isocentre) and adds an estimated object depth, M =
    SID / (SOD - depth) (Clunie), and neither is built, so every module's SID/SOD is used as the
    header states it, with the one spread STATED_LOG_SD. A factor of exactly 1 is passed over, as
    D5 and Cornerstone3D pass it:
    ERMF is SID/SOD, and 1 would put the detector at the point SOD runs to, the table's side nearest
    the patient in DX (PS3.3 C.8.11.5), so it is a factor never computed rather than one measured.
    A factor or a pair of distances passed over is recorded in `problems`."""
    ermf = getattr(ds, "EstimatedRadiographicMagnificationFactor", None)
    if ermf not in (None, ""):
        if float(ermf) > 1.0:
            return float(ermf), STATED_LOG_SD, "the Estimated Radiographic Magnification Factor (0018,1114)"
        problems.append("the Estimated Radiographic Magnification Factor (0018,1114) is %g, not above 1, so it states "
                        "no magnification (SID/SOD, row D5); it is passed over" % float(ermf))
    sid = getattr(ds, "DistanceSourceToDetector", None)
    sod = getattr(ds, "DistanceSourceToPatient", None)
    if sid not in (None, "") and sod not in (None, ""):
        if 0 < float(sod) < float(sid):
            return float(sid) / float(sod), STATED_LOG_SD, "SID/SOD (0018,1110 / 0018,1111)"
        problems.append("SID %g mm and SOD %g mm (0018,1110 / 0018,1111) give no magnification above 1, since the "
                        "source-to-patient distance is not the shorter; they are passed over" % (float(sid), float(sod)))
    return None


def caller_scale(pixel_mm: float, corrected: Optional[dict], stated: Optional[Tuple[float, float, str]]) -> dict:
    """The caller's pixel length at the detector in the header's place, over the magnification the
    header implies or states: only the pixel's length is replaced. The implied one is the
    unmagnified pixel over a Pixel Spacing given at the patient; else the stated factor; else the
    default."""
    basis = "the caller's pixel size at the detector"
    if corrected is not None and corrected["pixel_mm_at_detector"]:
        return scaled_at_detector(pixel_mm, basis + ", over the magnification the header's two spacings imply (%s)"
                                  % corrected["basis"], corrected["magnification"], corrected["log_sd"], "implied")
    if stated is not None:
        return scaled_at_detector(pixel_mm, basis + ", over " + stated[2], stated[0], stated[1])
    return scaled_at_detector(pixel_mm, basis)


def projection_scale(ds, override_mm: Optional[float] = None, problems: Optional[List[str]] = None) -> dict:
    """The pixel's length at the patient and the spread of its log, in the order of the note's
    decision rule, the report's rows D2 to D8: a fiducial calibration, a geometric correction,
    a Pixel Spacing smaller than the unmagnified pixel with no calibration type (corrected by a
    method not stated), the unmagnified pixel (Imager Pixel Spacing, else Nominal Scanned Pixel
    Spacing) over the magnification factor, over SID/SOD, or over the default magnification, and
    last a Pixel Spacing of unknown provenance. Every scale holds the same keys: pixel_mm at the
    patient, pixel_mm_at_detector where the header gives the unmagnified pixel (film.scale_of
    compares an annotation's pixel with it), the magnification between them, the spread of its log
    and the basis in words. A caller's pixel length (`override_mm`, at the detector) replaces only
    the header's pixel length, and is held to caller_value as the header's is to spacing_of. A Pixel
    Spacing of unknown provenance (row D8) is taken to be the detector's and divided by the default
    magnification, this module's choice (UNKNOWN_PROVENANCE_LOG_SD says what it costs). What the
    header says that cannot be used is appended to `problems`."""
    problems = [] if problems is None else problems
    override_mm = caller_value(override_mm, "--pixel-mm", LEAST_PIXEL_MM, inclusive=False)
    ps = spacing_of(ds, "PixelSpacing", "(0028,0030)", problems)
    raw = unmagnified_spacing(ds, problems)
    corrected = corrected_spacing(ds, ps, raw, problems)
    stated = stated_magnification(ds, problems)
    if override_mm is not None:
        return caller_scale(override_mm, corrected, stated)
    if corrected is not None:
        return corrected
    if raw is not None:
        if stated is not None:
            return scaled_at_detector(raw.length, "%s over %s" % (raw.name, stated[2]), stated[0], stated[1])
        return scaled_at_detector(raw.length, "%s, %s" % (raw.name, raw.plane))
    if ps is not None:
        return scaled_at_detector(ps, "Pixel Spacing (0028,0030) with no Imager or Nominal Scanned Pixel Spacing and "
                                  "no calibration type, whose correction the standard says cannot be determined, "
                                  "taken here as the detector's", None, UNKNOWN_PROVENANCE_LOG_SD)
    return unknown_scale("unknown: the file states no pixel spacing")


def shown_grey(ds, stored: np.ndarray, path: str) -> np.ndarray:
    """The image in one channel with bone bright, as Projection says. Grey pixels pass through
    their rescale, and MONOCHROME1, which shows high values dark, is turned over. Colour pixels (a
    secondary capture of a screen; pydicom 3 hands YCbCr back as RGB) become their luminance by
    LUMA, unrounded, as read_picture makes a colour picture grey. A palette or any other
    photometric interpretation is refused."""
    kind = str(getattr(ds, "PhotometricInterpretation", "") or "").strip().upper()
    if stored.ndim == 3 and stored.shape[-1] == 3:
        return stored.astype(np.float64) @ LUMA
    if kind not in ("MONOCHROME1", "MONOCHROME2", ""):
        raise SystemExit("%s has photometric interpretation %s; give the image as grey (MONOCHROME2) or RGB"
                         % (path, kind))
    pixels = rescaled(stored, getattr(ds, "RescaleSlope", None), getattr(ds, "RescaleIntercept", None))
    return pixels.max() - pixels if kind == "MONOCHROME1" else pixels


def projection_source(ds, path: str) -> str:
    """What kind of projection a DICOM file holds, by its exact SOP Class, or a refusal."""
    sop = str(getattr(ds, "SOPClassUID", ""))
    if sop in PROJECTION_CLASSES:
        return "DICOM %s" % PROJECTION_CLASSES[sop]
    if sop == CT_IMAGE and is_localizer(ds):
        return "DICOM CT localizer"
    if sop in SECONDARY_CAPTURE:
        return "DICOM %s" % SECONDARY_CAPTURE[sop]
    if sop in (CT_IMAGE, ENHANCED_CT):
        raise SystemExit("%s is a CT slice, not a projection; read it as a volume" % path)
    raise SystemExit("%s has SOP class %s, which is not a projection image read here" % (path, sop))


def projection_size(ds, path: str) -> Tuple[int, int]:
    """Rows (0028,0010) and Columns (0028,0011), the image's size, read without its pixel data."""
    rows, columns = getattr(ds, "Rows", None), getattr(ds, "Columns", None)
    if rows in (None, "") or columns in (None, ""):
        raise SystemExit("%s gives no Rows and Columns (0028,0010 and 0028,0011), so its size is not known" % path)
    return int(rows), int(columns)


def read_dicom_projection(path: str, pixel_mm: Optional[float] = None, with_pixels: bool = False) -> Projection:
    import pydicom
    ds = pydicom.dcmread(path, stop_before_pixels=not with_pixels)
    source = projection_source(ds, path)
    if int(getattr(ds, "NumberOfFrames", 1) or 1) > 1:
        raise SystemExit("%s holds %s frames; give one frame per file" % (path, ds.NumberOfFrames))
    problems: List[str] = []
    scale = projection_scale(ds, pixel_mm, problems)
    pixels = shown_grey(ds, pixels_of(ds), path) if with_pixels else None
    if scale["pixel_mm"] is None and str(getattr(ds, "SOPClassUID", "")) in SECONDARY_CAPTURE:
        problems.append("a secondary capture with no Pixel Spacing or Nominal Scanned Pixel Spacing: its scale is "
                        "unknown, never 1 mm")
    if scale["pixel_mm"] is None:
        problems.append("no pixel spacing: the chords stay in pixels and the scale is unknown")
    return Projection(size=projection_size(ds, path), sha256=sha256_of(path), source=source, scale=scale,
                      header=dicom_covariates(ds), problems=problems, pixels=pixels)
