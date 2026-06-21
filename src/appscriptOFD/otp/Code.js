const SHEET_ID = '1zR-utnh-drA4eVUWuASOboc7U1wfwnUxgbXDQk0jmMs';

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.openById(SHEET_ID);
    let sheet = ss.getSheetByName("SMS_OTP");
    
    // Buat sheet jika belum ada
    if (!sheet) {
      sheet = ss.insertSheet("SMS_OTP");
      const headers = ["Timestamp", "Pengirim", "OTP", "Device", "Body SMS", "Dicatat Pada"];
      sheet.appendRow(headers);
      
      // Format header
      const headerRange = sheet.getRange(1, 1, 1, headers.length);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#1a73e8");
      headerRange.setFontColor("#ffffff");
      sheet.setFrozenRows(1);
    }
    
    // Waktu pencatatan (Server Time)
    const serverTime = Utilities.formatDate(new Date(), "GMT+7", "yyyy-MM-dd HH:mm:ss");
    
    // Append data
    sheet.appendRow([
      data.timestamp,
      data.sender,
      data.otp,
      data.device,
      data.body,
      serverTime
    ]);
    
    return ContentService.createTextOutput(JSON.stringify({ "status": "ok", "row": sheet.getLastRow() }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({ "status": "running", "info": "SMS OTP Receiver is active" }))
    .setMimeType(ContentService.MimeType.JSON);
}
