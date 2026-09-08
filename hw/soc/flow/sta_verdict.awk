# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# The verdict rule, in one file, for every STA flow under hw/soc/.
#
#   awk -v cfg=<name> -v per=<period> -v corners="<list>" \
#       -f sta_verdict.awk  <groups.rpt> <sta.log>
#
# WHY IT IS A FILE. flow/sta_ibex.sh's header states the rule at length:
# every check that is reported is also judged, the verdict names its own
# scope, and there is no bare pass token. That rule was written once,
# for one design, and docs/45 needed it for a second -- soc_top, timed
# whole. Two copies of a verdict rule that must agree and that nothing
# compares is the same defect docs/44 section 5.4 refused for a parity
# matrix, one level up. So the rule lives here and both flows call it.
#
# Splitting it out changes no output: flow/sta_ibex.sh's printed
# slack.rpt is byte-identical before and after, which docs/45 section 4.1
# records as a measurement rather than an intention.
#
# The verdict is formed from the ALL-GROUP worst slacks, so no path group
# can fail behind a green summary line. The per-group decomposition is
# printed for diagnosis and never narrows the verdict. A caller that
# wants to gate on a subset reads a GATE line and is on record, in its
# own source, as having gated on that subset and nothing else.

FNR==NR {
  if ($1=="GROUP") g[$2 " " $3] = $4
  next
}
/^WORSTSLACK setup/ { su[$3]=$NF; if (ns=="" || $NF+0 < ns+0) { ns=$NF; nc=$3 } }
/^WORSTSLACK hold/  { ho[$3]=$NF; if (nh=="" || $NF+0 < nh+0) { nh=$NF; hc=$3 } }
END {
  n = split(corners, cs, " ")
  printf "  %-5s  %-10s %-10s | %-10s %-10s\n", \
         "corner", "setup", "hold", "setup_sync", "setup_async"
  for (i=1; i<=n; i++) {
    c = cs[i]
    printf "  %-5s  %-10s %-10s | %-10s %-10s\n", c, su[c], ho[c], \
           g["setup_sync " c], g["setup_async " c]
  }
  # Worst-across-corners per check, for callers that gate on a named
  # subset. A caller that reads GATE setup_sync is on record as having
  # gated on setup_sync and nothing else.
  ss = ""; sc = ""
  for (i=1; i<=n; i++) {
    c = cs[i]; v = g["setup_sync " c]
    if (v != "-" && (ss == "" || v+0 < ss+0)) { ss = v; sc = c }
  }
  printf "GATE setup_all  %s %s\n", ns, nc
  printf "GATE setup_sync %s %s\n", ss, sc
  printf "GATE hold       %s %s\n", nh, hc

  fails = ""
  if (ns+0 < 0) fails = fails sprintf("setup(%s,%s) ", ns, nc)
  if (nh+0 < 0) fails = fails sprintf("hold(%s,%s) ", nh, hc)
  printf "  worst setup %s at %s, worst hold %s at %s\n", ns, nc, nh, hc
  if (fails == "")
    printf "VERDICT %s period=%s ns ALL_CHECKS_MET (setup+hold, %d corners)\n", \
           cfg, per, n
  else
    printf "VERDICT %s period=%s ns NOT_MET: %s\n", cfg, per, fails
}
