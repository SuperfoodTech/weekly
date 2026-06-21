function doPost(e) {
  var sheetName = e.parameter.sheet;
  var data = JSON.parse(e.postData.contents);
  var clearSheet = e.parameter.clear === 'true';
  
  if (!sheetName) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: "No sheet name provided"}))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName);
  
  if (!sheet) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: "Sheet not found: " + sheetName}))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // Hapus data sebelumnya jika parameter clear=true
  if (clearSheet && sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).clearContent();
  }
  
  if (data && data.length > 0) {
    var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    var rows = [];
    
    for (var i = 0; i < data.length; i++) {
      var row = [];
      for (var j = 0; j < headers.length; j++) {
        var header = headers[j];
        row.push(data[i][header] || "");
      }
      rows.push(row);
    }
    
    if (rows.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, headers.length).setValues(rows);
    }
    
    return ContentService.createTextOutput(JSON.stringify({status: "success", rows_added: rows.length}))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  return ContentService.createTextOutput(JSON.stringify({status: "error", message: "No data provided"}))
    .setMimeType(ContentService.MimeType.JSON);
}
