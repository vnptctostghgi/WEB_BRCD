DEFINE thang        = :THANG
DEFINE loaihd       = :LOAIHD
DEFINE doituong     = :DOITUONGKHAC
DEFINE trangthaitb  = :TRANGTHAITB
DEFINE dv_ngpt      = :DVNGPT
DEFINE kykh         = :KYKH
DEFINE tenchitieu   = :TENCHITIEU
DEFINE donvi        = :DONVI

WITH th AS (
    SELECT
        COUNT(CASE WHEN ptm.loaitb_id IN (58) THEN ptm.ma_tb END) AS fiber_th,
        COUNT(CASE WHEN ptm.loaitb_id IN (61,171) THEN ptm.ma_tb END) AS mytv_th,
        COUNT(CASE WHEN ptm.loaitb_id IN (210,274) THEN ptm.ma_tb END) AS mesh_th,
        COUNT(CASE WHEN ptm.loaitb_id IN (224,222) THEN ptm.ma_tb END) AS camera_th
    FROM v_ds_thuebao ptm, v_ds_thuebao_combo cb, v_ds_thuebao_daccoc dc
    WHERE 1=1
      AND (TRIM('&loaihd') IS NULL OR INSTR(','||REPLACE('&loaihd',' ','')||',', ','||TO_CHAR(ptm.loaihd_id)||',') > 0)
      AND (TRIM('&doituong') IS NULL OR INSTR(','||REPLACE('&doituong',' ','')||',', ','||TO_CHAR(ptm.doituong_id)||',') = 0)
      AND (TRIM('&trangthaitb') IS NULL OR INSTR(','||REPLACE('&trangthaitb',' ','')||',', ','||TO_CHAR(ptm.trangthaitb_id)||',') > 0)
      AND (TRIM('&dv_ngpt') IS NULL OR UPPER(ptm.dv_ngpt) LIKE '%'||UPPER(TRIM('&dv_ngpt'))||'%')
      AND TO_DATE(ptm.ngay_ht,'DD/MM/YYYY') >= CASE
            WHEN TRIM('&thang') IS NULL THEN TRUNC(SYSDATE,'MM')
            WHEN INSTR('&thang','-') > 0 THEN TO_DATE('01/'||SUBSTR('&thang',1,INSTR('&thang','-')-1),'DD/MM/YYYY')
            ELSE TO_DATE('01/&thang','DD/MM/YYYY') END
      AND TO_DATE(ptm.ngay_ht,'DD/MM/YYYY') < CASE
            WHEN TRIM('&thang') IS NULL THEN ADD_MONTHS(TRUNC(SYSDATE,'MM'),1)
            WHEN INSTR('&thang','-') > 0 THEN ADD_MONTHS(TO_DATE('01/'||SUBSTR('&thang',INSTR('&thang','-')+1),'DD/MM/YYYY'),1)
            ELSE ADD_MONTHS(TO_DATE('01/&thang','DD/MM/YYYY'),1) END
      AND ptm.phanvung_id = cb.phanvung_id(+)
      AND ptm.thuebao_id = cb.thuebao_id(+)
      AND ptm.tocdo_id = cb.tocdo_id(+)
      AND ptm.loaitb_id = cb.loaitb_id(+)
      AND ptm.phanvung_id = dc.phanvung_id(+)
      AND ptm.thuebao_id = dc.thuebao_id(+)
), kh AS (
    SELECT
        SUM(CASE WHEN UPPER(kh.machitieu)='SL_FIBER_COE_V2' THEN kh.kehoach ELSE 0 END) AS fiber_kh,
        SUM(CASE WHEN UPPER(kh.machitieu)='SL_MYTV_COE_V2' THEN kh.kehoach ELSE 0 END) AS mytv_kh,
        SUM(CASE WHEN UPPER(kh.machitieu)='SL_MESH_COE_V2' THEN kh.kehoach ELSE 0 END) AS mesh_kh,
        SUM(CASE WHEN UPPER(kh.machitieu)='SL_CAM_COE_V2' THEN kh.kehoach ELSE 0 END) AS camera_kh
    FROM kh_nam_2026 kh
    WHERE (
        (TRIM('&kykh') IS NULL AND kh.kykh=TO_NUMBER(TO_CHAR(SYSDATE,'YYYYMM')))
        OR (TRIM('&kykh')='1' AND kh.kykh>TO_NUMBER(TO_CHAR(SYSDATE,'YYYY')) AND kh.kykh<TO_NUMBER(TO_CHAR(SYSDATE,'YYYYMM')))
        OR (TRIM('&kykh')='2' AND kh.kykh>TO_NUMBER(TO_CHAR(SYSDATE,'YYYY')) AND kh.kykh<TO_NUMBER(TO_CHAR(ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1),'YYYYMM')))
        OR (REGEXP_LIKE(TRIM('&kykh'),'^[0-9]{4}$') AND kh.kykh=TO_NUMBER(TRIM('&kykh')))
        OR (REGEXP_LIKE(TRIM('&kykh'),'^[0-9]{2}/[0-9]{4}$') AND kh.kykh=TO_NUMBER(TO_CHAR(TO_DATE('01/'||TRIM('&kykh'),'DD/MM/YYYY'),'YYYYMM')))
      )
      AND (TRIM('&tenchitieu') IS NULL OR UPPER(kh.tenchitieu) LIKE '%'||UPPER(TRIM('&tenchitieu'))||'%')
      AND (TRIM('&donvi') IS NULL OR UPPER(kh.donvi) LIKE '%'||UPPER(TRIM('&donvi'))||'%')
)
SELECT
    NVL(th.fiber_th,0) AS fiber_th, NVL(kh.fiber_kh,0) AS fiber_kh,
    NVL(th.mytv_th,0) AS mytv_th, NVL(kh.mytv_kh,0) AS mytv_kh,
    NVL(th.mesh_th,0) AS mesh_th, NVL(kh.mesh_kh,0) AS mesh_kh,
    NVL(th.camera_th,0) AS camera_th, NVL(kh.camera_kh,0) AS camera_kh
FROM th CROSS JOIN kh
