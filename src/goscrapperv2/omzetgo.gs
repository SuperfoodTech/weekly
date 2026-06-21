function doPost(e) {
  try {
    // 1. Mengambil data JSON yang dikirimkan
    var data = JSON.parse(e.postData.contents);
    var username = data.username;
    
    // 2. Akses Spreadsheet (Menggunakan ID manual sesuai permintaan)
    var spreadsheetId = "1zR-utnh-drA4eVUWuASOboc7U1wfwnUxgbXDQk0jmMs";
    var ss = SpreadsheetApp.openById(spreadsheetId);
    var sheet = ss.getSheetByName("Baseline Report");
    
    if (!sheet) {
      return ContentService.createTextOutput("Error: Sheet 'Trial Baseline Report' tidak ditemukan.");
    }
    
    // 3. Ambil data di Kolom A untuk mencari baris Username
    var lastRow = sheet.getLastRow();
    var userList = sheet.getRange(1, 1, lastRow, 1).getValues();
    var targetRow = -1;
    
    for (var i = 0; i < userList.length; i++) {
      if (userList[i][0] == username) {
        targetRow = i + 1; // Baris ditemukan
        break;
      }
    }
    
    if (targetRow != -1) {
      // 4. Update Kolom J, K, L (Index kolom 10, 11, 12)
      // Diasumsikan data dikirim dengan key: omzet1, omzet2, omzet3
      sheet.getRange(targetRow, 10).setValue(data.omzet1); // Kolom J
      sheet.getRange(targetRow, 11).setValue(data.omzet2); // Kolom K
      sheet.getRange(targetRow, 12).setValue(data.omzet3); // Kolom L
      
      // 5. Update Kolom N, O, P (Index kolom 14, 15, 16)
      // Diasumsikan data dikirim dengan key: extra1, extra2, extra3
      sheet.getRange(targetRow, 14).setValue(data.extra1); // Kolom N
      sheet.getRange(targetRow, 15).setValue(data.extra2); // Kolom O
      sheet.getRange(targetRow, 16).setValue(data.extra3); // Kolom P
      
      return ContentService.createTextOutput("Berhasil update data untuk user: " + username);
    } else {
      return ContentService.createTextOutput("Error: Username '" + username + "' tidak ditemukan di kolom A.");
    }
    
  } catch (err) {
    return ContentService.createTextOutput("Error: " + err.toString());
  }
}