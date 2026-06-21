function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    
    // Mencoba mengambil spreadsheet yang aktif (jika script ditempel di dalam file sheet) - update_test
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    
    // Jika ss masih null, berarti script ini standalone, gunakan ID di bawah ini
    if (!ss) {
      // GANTI ID DI BAWAH INI JIKA MENGGUNAKAN STANDALONE SCRIPT
      var manualId = '1zR-utnh-drA4eVUWuASOboc7U1wfwnUxgbXDQk0jmMs'; 
      ss = SpreadsheetApp.openById(manualId);
    }
    
    var sheetName = data.sheetName || 'Trial Baseline Report';
    var sheet = ss.getSheetByName(sheetName);
    
    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({
        "status": "error", 
        "message": "Sheet bernama '" + sheetName + "' tidak ditemukan"
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    var values = sheet.getDataRange().getValues();
    
    var username = data.username;
    var found = false;
    
    // Loop untuk mencari username (Akses) di kolom A
    for (var i = 1; i < values.length; i++) {
      if (values[i][0] == username) { 
        var row = i + 1;
        // Update kolom Omzet (G, H, I -> kolom 7, 8, 9)
        sheet.getRange(row, 7).setValue(data.omzet1).setNumberFormat('Rp#,##0');
        sheet.getRange(row, 8).setValue(data.omzet2).setNumberFormat('Rp#,##0');
        sheet.getRange(row, 9).setValue(data.omzet3).setNumberFormat('Rp#,##0');
        
        // Update kolom Order (K, L, M -> kolom 11, 12, 13)
        sheet.getRange(row, 11).setValue(data.order1);
        sheet.getRange(row, 12).setValue(data.order2);
        sheet.getRange(row, 13).setValue(data.order3);
        
        found = true;
        break;
      }
    }
    
    if (!found) {
      return ContentService.createTextOutput(JSON.stringify({
        "status": "error", 
        "message": "Username '" + username + "' tidak ditemukan di kolom Akses"
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    return ContentService.createTextOutput(JSON.stringify({"status": "success"}))
      .setMimeType(ContentService.MimeType.JSON);
    
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      "status": "error", 
      "message": err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
