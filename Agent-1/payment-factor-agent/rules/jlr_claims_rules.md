# JLR Claims Data Rules (`**/jlr*`, `**/claims*`)

- Date fields: `Repair_Date` is `dd-MMM-yyyy` string (do NOT parse as `yyyy-MM-dd`); `I_INCIDENT_DATE` is a proper `date` type for joins; `Repair_Month` is `yyyy-MM` string.
- DTC data: `DM_DTCs` on IQM claim table stopped being populated from 2024. Topix DTCs are in `bci_rbs_prod.raw.dxq_jlr_service_topix_dtc_reads` (576M rows); SDD DTCs in `bci_rbs_prod.raw.dxq_jlr_service_dtc_reads` (990M rows). Join by VIN + date proximity (I_INCIDENT_DATE +/- 7 days).
- IQM project allocation: "Not in an IQM Project" does NOT mean unallocated -- 953K of these have `P_PROJECT_REFERENCE` populated (hidden projects). Three buckets: Visible IQM (416K), Hidden IQM (715K), Truly Unallocated (766K).
- MPN/SQW: Join key `IC_SERV_PART_NUMBER` = MPN `Cust P.No`. "Not RB" in MPN does not mean Bosch never supplied it -- historical parts may still be under warranty.
- Connection: profile `edocument`, proxy `http://rb-proxy-de.bosch.com:8080`, warehouse `f9f9ba24a8e2d807` (QLT Serverless). All queries read-only SELECT against `bci_rbs_prod`.
