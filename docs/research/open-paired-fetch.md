# The open paired sets, fetched on 2026-11-02

Source: a local session of the owner's, the night of 1 to 2 November 2026, which fetched the open sets the paired CT and X-ray survey of that night ranked "can be got now" (the survey is the session's own report and is not in this repository; its sets are spine-datasets #183 to #186 and the new #388). Every number below was read from a grid job's log or from the verification jobs' own walk of each landing, named beside it.

## Why the sets came as lists of series

Three of the four are a few thousand series inside TCIA collections of hundreds of gigabytes (CT COLONOGRAPHY 496.7 GB, COVID-19-NY-SBU over 500 GB), and the platform's idc route (grid/platform-fetch.sbatch) takes a collection whole. So each set is a named selection of grid/series_select.py: a rule applied on the grid to the catalogue as it stands and to what the grid already holds, never a committed list of patients. The rule writes the series manifest into the landing's meta folder; the size rule (grid/size-rule.sh) admits the exact bytes that manifest names before any byte lands; and spinesurg-ct-nnunet's acquisition_fetch.sh fetches each series and checks its instance count against the catalogue (grid/open-pairs.sbatch). IDC v24 holds 23 of CMB-MML's 29 XA series and 12 of its 130 CR series, so the CMB sets came through NBIA instead.

The fourth part is the CT series CTSpine1K's COLONOG vertebra masks were drawn on. Their images were retired from the grid on 2026-10-31 (spine-datasets #379), and a mask meets the same exam's localizer only through its series' geometry, so grid/idc_headers.py reads each instance's header from IDC's public bucket by one range request and keeps it up to the Pixel Data, which is never written. The smoke job of 2026-11-02 measured those headers at 1,890 to 1,896 bytes (24 instances of 4 series), so 16 KiB is read of each half-megabyte object, and the size rule is told that bound.

## What landed

| Set (spine-datasets record) | Landing under /rs/rs_grp_oschome/go2432/data | Job | Series verified | Patients | DICOM files | Bytes |
|---|---|---|---|---|---|---|
| CT COLONOGRAPHY localizers (tcia_ct_localizers, #186) | tcia_ct_localizers | 40940462 | 1,552 of 1,552 | 725 | 2,413 | 2,345,124,626 |
| COVID-19-NY-SBU abdominal films and localizers (covid19_ny_sbu_films, #185) | covid19_ny_sbu_films | 40940463 | 247 of 247 | 27 | 300 | 3,132,239,638 |
| CMB-MML and CMB-AML XA frames with CT (cmb_xa_frames, #183) | cmb_xa_frames | 40940464 | 67 of 67 | 16 | 1,895 | 1,077,996,694 |
| CMB-MML films with CT (cmb_mml_radiographs, #184) | cmb_mml_radiographs | 40940465 | 149 of 149 | 11 | 2,441 | 3,045,827,156 |
| CT COLONOGRAPHY masked CT headers (tcia_ct_localizers, #186) | tcia_ctc_ct_headers | 40940480 | HEADERS_SERIES | HEADERS_PATIENTS | HEADERS_FILES | HEADERS_BYTES |

FORCAST-EST (spine-datasets #388), six zips of 4,629,411,361 bytes from heiDATA (doi:10.11588/data/GIWRQA, CC BY 4.0), came the other way: a manifest with each file's md5 from heiDATA's dataset API, which the promoter fetched into /rs/rs_grp_oschome/shared/datasets/heidata_forcast_est/raw and froze (promoter job 40932486, spine-datasets #390 and #396).

The verification job (40940602) walked each landing against its manifest: every series folder holds the catalogue's count of files and every file reads as DICOM. What the headers say, as counts:

- The CT COLONOGRAPHY localizers are CT images of type LOCALIZER: 2,071 frontal and 342 lateral by their orientation; 2,328 of 2,413 carry the source to patient and source to image distances; all carry the position, orientation, spacing and frame of reference a projection needs. Siemens 1,500, GE 828, Philips 77, Toshiba 8.
- The SBU films are 128 CR and 66 DX AP portable abdominal films; the 53 localizer series are one frontal and one lateral image each.
- The CMB XA images are 813, the positioner angles in 41 of them and the source to image distance in all; 772 of them carry a patient orientation and position, the DynaCT stored as XA.
- HEADERS_PAIRING

## What this does not settle

None of these is a C-arm cone-beam sweep of a living lumbar spine: a localizer is the scanner's own fan-beam line scan, the films need registration to their CT, and the XA frames are single captures. FORCAST-EST is a phantom, and whether its field holds the sacrum is not read yet. None of them joins any loop until a PREREG of its own names it.
