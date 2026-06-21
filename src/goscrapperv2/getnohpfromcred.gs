function doGet(e) {
  var sheetName = "Credential";
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName);
  
  if (!sheet) {
    return ContentService.createTextOutput("Sheet tidak ditemukan").setMimeType(ContentService.MimeType.TEXT);
  }

  var data = sheet.getDataRange().getValues();
  var appColIndex = 3;   // Kolom D
  var phoneColIndex = 26; // Kolom AA
  
  var phoneNumbers = []; // Tempat menyimpan banyak nomor

  for (var i = 1; i < data.length; i++) {
    if (data[i].length > phoneColIndex) {
      var appValue = data[i][appColIndex].toString().trim().toLowerCase();
      
      if (appValue === "gofood") {
        var phone = data[i][phoneColIndex].toString().trim();
        if (phone !== "") {
          phoneNumbers.push(phone); // Masukkan nomor ke dalam daftar
        }
      }
    }
  }

  if (phoneNumbers.length > 0) {
    // Menggabungkan semua nomor dengan pemisah koma agar mudah diproses Python
    return ContentService.createTextOutput(phoneNumbers.join(","))
      .setMimeType(ContentService.MimeType.TEXT);
  } else {
    return ContentService.createTextOutput("Tidak ada nomor GoFood ditemukan");
  }
}