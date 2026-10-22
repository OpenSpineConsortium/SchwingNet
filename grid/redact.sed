# What grid/gate.sh 'status' masks in every line it shows of a job's log or a stage report
# (issue #80), run as sed -r -f, which GNU sed 4.2 on the login node reads. A net, not a proof:
# the audit in issue #80 found which jobs' logs can carry a DICOM header value, a person key made
# from one or a credential, and status shows those jobs' logs only as shapes (grid/log-shapes.awk)
# before this runs. Every rule leaves the shape of the line and takes the value.
#
# A line that names a DICOM element by its tag or its keyword, or that pydicom wrote about a
# value it read, goes whole: its value could sit anywhere on it.
/\([0-9A-Fa-f]{4}, ?[0-9A-Fa-f]{4}\)/s/.*/[a line withheld: it names a DICOM tag]/
/(Patient|Accession|Institution|Physician|Operators|StationName|DeviceSerial|InstanceUID|StudyDate|SeriesDate|AcquisitionDate|ContentDate|StudyTime|StudyID|Invalid value for VR)/Is/.*/[a line withheld: it names a DICOM element]/
# Credentials: a URL's user and password, a signed link's query, a key=value or key: value whose
# key names a secret, a netrc line's password, a header's token, and the prefixes of common tokens.
s#(://)[^/@[:space:]]+@#\1<withheld>@#g
s#([?&;](X-Amz-[A-Za-z-]+|Signature|signature|Sig|sig|token|access_token|auth|key|apikey|api_key|Expires|Key-Pair-Id|Policy|Credential|code)=)[^&[:space:]"']+#\1<withheld>#g
s#((password|passwd|pwd|secret|token|api[_-]?key|apikey|authorization|cookie|credential)s?["']?[[:space:]]*[:=][[:space:]]*["']?)[^[:space:]"',;]+#\1<withheld>#Ig
s#\b(password|passwd)[[:space:]]+[^[:space:]]+#\1 <withheld>#Ig
s#\b(Bearer|Basic|token)[[:space:]]+[A-Za-z0-9._~+/=-]{8,}#\1 <withheld>#Ig
s#\b(hf_|ghp_|gho_|ghs_|ghu_|ghr_|github_pat_|glpat-|xox[abprs]-|sk-)[A-Za-z0-9_-]{8,}#<withheld>#g
s#\b(AKIA|ASIA)[0-9A-Z]{16}\b#<withheld>#g
# The person keys bank.py, ingest.py and catalog.py name in their refusals, <source>:<key> or a
# bank's own key alone, before the shapes below cut a key in two.
s#\bperson [^[:space:]]+ holds more than#person <withheld> holds more than#g
s#\(first [^)]*\)#(first <withheld>)#g
s#\b([a-z][a-z0-9_]*):([A-Za-z0-9][^[:space:],;)'"]*)#\1:<withheld>#g
# 32 hex digits are VinDr's hashed UIDs and identifiers, 40 a W&B key; a sha256 of a frame's bytes
# (64) and a shard's digest (12) stay, since they name content and not a person.
s#\b([0-9a-fA-F]{32}|[0-9a-fA-F]{40})\b#<hex withheld>#g
# DICOM values by their shape: a UID (five or more dotted numbers), a date as DICOM writes it
# (YYYYMMDD) or quoted, and a value pydantic or icontract quotes back.
s#\b[0-9]+(\.[0-9]+){4,}\b#<uid withheld>#g
# Bounded by any non-digit, not by \b, since an underscore is a word character and a file name
# such as scan_19650312.dcm carries a date with no word boundary before it; run twice, since two
# dates one character apart share that character and g takes only the first.
s#(^|[^0-9])(19|20)[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])([^0-9]|$)#\1<date withheld>\5#g
s#(^|[^0-9])(19|20)[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])([^0-9]|$)#\1<date withheld>\5#g
s#(["'])(19|20)[0-9]{2}-?(0[1-9]|1[0-2])-?(0[1-9]|[12][0-9]|3[01])([T ][0-9:.]*)?["']#\1<date withheld>\1#g
s#input_value=.*(, input_type=[A-Za-z_]+\])#input_value=<withheld>\1#g
s#input_value=[^<].*#input_value=<withheld>#
s#^([[:space:]]*[A-Za-z_][A-Za-z0-9_.]*(\[[^]]*\])? was ).*#\1<withheld>#
