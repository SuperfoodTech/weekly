const CONFIG = {
    // Template Document ID yang baru (Google Docs Asli)
    TEMPLATE_ID: "1RVyvMOpYD53jl_u96CjJMHDWX8UMZqE8Xp9hfVoBX9I",

    // ID Folder tujuan untuk menyimpan PDF
    OUTPUT_FOLDER_ID: "1C5nuklD-v6gw8Ge2ZjUuUBnHwHPIkJum"
};

function doPost(e) {
    const lock = LockService.getScriptLock();
    lock.tryLock(10000);

    try {
        if (!e.postData || !e.postData.contents) {
            return responseJSON({ success: false, error: "No payload provided" });
        }

        const data = JSON.parse(e.postData.contents);

        if (data.action === "generate_baseline_pdf") {
            return generateBaselinePDF(data);
        }

        return responseJSON({ success: false, error: "Invalid action" });
    } catch (error) {
        return responseJSON({ success: false, error: error.toString() });
    } finally {
        lock.releaseLock();
    }
}

function generateBaselinePDF(data) {
    // 1. Dapatkan Template
    const templateFile = DriveApp.getFileById(CONFIG.TEMPLATE_ID);

    // 2. Tentukan Folder Output
    let targetFolder = DriveApp.getRootFolder();
    if (CONFIG.OUTPUT_FOLDER_ID) {
        try {
            targetFolder = DriveApp.getFolderById(CONFIG.OUTPUT_FOLDER_ID);
        } catch (e) { }
    }

    // Nama file PDF yang dihasilkan
    const newFilename = `Baseline_Report_${data.nama_outlet}_${data.tanggal}_${data.bulan}_${data.tahun}`;

    // 3. Buat Duplikat Sementara (Temp Doc)
    const tempFile = templateFile.makeCopy(newFilename + "_TEMP", targetFolder);
    const tempDoc = DocumentApp.openById(tempFile.getId());
    const body = tempDoc.getBody();

    // Helper functions for parsing and formatting
    const parseRupiah = (val) => {
        if (!val) return 0;
        const clean = val.replace(/Rp/g, "").replace(/\./g, "").replace(/\s/g, "").replace(/,/g, ".");
        const num = parseFloat(clean);
        return isNaN(num) ? 0 : num;
    };

    const parseOrder = (val) => {
        if (!val) return 0;
        const clean = val.replace(/\s/g, "").replace(/,/g, ".");
        const num = parseFloat(clean);
        return isNaN(num) ? 0 : num;
    };

    const formatRupiah = (val) => {
        const formatted = Math.round(val).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return "Rp " + formatted;
    };

    const totalOmzetVal = parseRupiah(data.omzet_go) + parseRupiah(data.omzet_gr) + parseRupiah(data.omzet_sf);
    const totalOrderVal = parseOrder(data.order_go) + parseOrder(data.order_gr) + parseOrder(data.order_sf);

    const totalOmzet = data.total_omzet || formatRupiah(totalOmzetVal);
    const totalOrder = data.total_order || String(Number(totalOrderVal.toFixed(1)));

    // 4. Siapkan Data Replacement
    const replacements = {
        '<<Tanggal>>': data.tanggal || "-",
        '<<Bulan>>': data.bulan || "-",
        '<<Tahun>>': data.tahun || "-",
        '<<Owner>>': data.owner || "-",
        '<<Nama Outlet>>': data.nama_outlet || "-",
        '<<Omzet Go>>': data.omzet_go || "Rp 0",
        '<<Order Go>>': data.order_go || "0",
        '<<Omzet Gr>>': data.omzet_gr || "Rp 0",
        '<<Order Gr>>': data.order_gr || "0",
        '<<Omzet SF>>': data.omzet_sf || "Rp 0",
        '<<Order SF>>': data.order_sf || "0",
        '<<Total Omzet>>': totalOmzet,
        '<<Total Order>>': totalOrder
    };

    // 5. Eksekusi Replace Text di seluruh dokumen
    for (const [key, val] of Object.entries(replacements)) {
        body.replaceText(key, val);
    }

    tempDoc.saveAndClose();

    // 6. Hapus PDF lama jika ada dengan nama yang sama
    const targetPdfName = newFilename + ".pdf";
    const existingFiles = targetFolder.getFilesByName(targetPdfName);
    while (existingFiles.hasNext()) {
        existingFiles.next().setTrashed(true);
    }

    // 7. Konversi ke PDF
    const pdfBlob = tempFile.getAs(MimeType.PDF);
    const pdfFile = targetFolder.createFile(pdfBlob).setName(targetPdfName);

    // 8. Bersihkan Temp Doc
    tempFile.setTrashed(true);

    return responseJSON({
        success: true,
        message: "PDF Baseline berhasil dibuat!",
        pdf_url: pdfFile.getUrl(),
        pdf_name: targetPdfName
    });
}

function responseJSON(data) {
    return ContentService.createTextOutput(JSON.stringify(data))
        .setMimeType(ContentService.MimeType.JSON);
}
