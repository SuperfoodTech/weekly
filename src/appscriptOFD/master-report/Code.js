// Version: 1.3.0 - Strict Mapping & Fixed Header Order
var GRAB_HEADERS = [
  "Flag", "Month", "Merchant Name", "Merchant ID", "Store Name", "Store ID", 
  "Updated On", "Created On", "Type", "Category", "Subcategory", "Status", 
  "Transaction ID", "Linked Transaction ID", "Partner transaction ID 1", 
  "Partner transaction ID 2", "Long Order ID", "Short Order ID", "Booking ID", 
  "Order Channel", "Order Type", "Payment Method", "Receiving account / Source of fund", 
  "Terminal ID", "Channel", "Offer Type", "Grab Fee (%)", "Points Multiplier", 
  "Points Issued", "Settlement ID", "Transfer Date", "Amount", "Tax on Order Value", 
  "Restaurant Packaging Charge", "Non-Member Fee", "Restaurant Service Charge", 
  "Offer", "Discount (Merchant-Funded)", "Delivery Fee Discount (Merchant-Funded)", 
  "Delivery Charge (Grab Online Store)", "Delivery Charge (Merchant Delivery)", 
  "GrabExpress Delivery Service Fee", "Net Sales", "Net MDR", "Tax on MDR", 
  "Grab Fee", "Marketing success fee", "Delivery Commission", "Channel Commission", 
  "Order commission", "GrabFood / GrabMart Other Commission", "GrabKitchen Commission", 
  "GrabKitchen Other Commission", "Withholding Tax", "Total", "Tax on MDR (%)", 
  "Delivery Commission (%)", "Channel Commission (%)", "Order Commission (%)",
  "Tax on GrabFood / GrabMart Commission, Adjustments, Ads",
  "Tax on Total GrabKitchen Commission", "Cancellation Reason", "Cancelled by", 
  "Reason for Refund", "Description", "Incident group", "Incident alias", 
  "Customer refund Item", "Appeal link", "Appeal status", "Package/Voucher Used", 
  "Attributed Service Fee", "Attributed Promo", "Move to OE/OP"
];

var SHOPEE_HEADERS = [
  "Flag","Month","Store ID","Store name","Transaction type","Transaction ID (Order ID)",
  "Complete Time","Status","Food original price","Item discounts","Flash sale discount",
  "Surcharge fee","Merchant Voucher Deals Subsidy","Platform Flash Sale Subsidy",
  "Food Voucher Subsidy","Food Direct Discount","Transaction amount","Checkout Murah Price",
  "Notes","Net Sales","Commission","Revenue","Move to OE/OP"
];

var MAPPING_CONFIG = {
  "Grab": {
    "GrabFood / GrabMart Other Commission": "Step-up commission",
    "Tax on GrabFood / GrabMart Commission, Adjustments, Ads": "Tax on GrabFood/GrabMart commission, adjustments, ads"
    // Kolom lain diasumsikan namanya sama dengan key-nya
  },
  "Shopee": {}
};

// Version: 1.3.1 - Support Hardcoded Spreadsheet ID
var SPREADSHEET_ID = "1T2XIobyaNmcuWczUsIArb3f_d1Qnst4-BRL0KS5bS8o"; // ID Spreadsheet yang Anda berikan

function doPost(e) {
  var sheetName = e.parameter.sheet;
  var data = JSON.parse(e.postData.contents);
  var clearSheet = e.parameter.clear === 'true';
  
  if (!sheetName) return createResponse("error", "No sheet name provided");
  
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Fallback ke hardcoded ID jika ss null (standalone script)
  if (!ss && SPREADSHEET_ID) {
    ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  }
  
  if (!ss) return createResponse("error", "Spreadsheet connection failed. Please set SPREADSHEET_ID.");
  
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) return createResponse("error", "Sheet not found: " + sheetName);

  var headers = (sheetName === "Grab") ? GRAB_HEADERS : SHOPEE_HEADERS;
  var mapping = MAPPING_CONFIG[sheetName] || {};

  if (clearSheet) {
    sheet.clearContents();
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  
  // Gunakan header resmi (headers) bukan currentHeaders agar mapping konsisten
  if (data && data.length > 0) {
    var rows = data.map(function(item) {
      return headers.map(function(gsheet_col) {
        var master_key = mapping[gsheet_col] || gsheet_col;
        return item[master_key] || item[gsheet_col] || "";
      });
    });
    
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, headers.length).setValues(rows);
    
    // SINKRONISASI KE SHEET ORDER SETELAH DATA MASUK
    syncOrderSheet(ss);
    
    return createResponse("success", rows.length + " rows added");
  }
  
  return createResponse("error", "No data provided");
}

/**
 * Fungsi untuk sinkronisasi ID dari Grab & Shopee ke sheet Order
 */
function syncOrderSheet(ss) {
  var orderSheet = ss.getSheetByName("Order");
  if (!orderSheet) return;

  var grabSheet = ss.getSheetByName("Grab");
  var shopeeSheet = ss.getSheetByName("Shopee");

  // 1. Ambil ID yang sudah ada di sheet Order (Kolom Q / Long Order ID)
  var orderData = orderSheet.getDataRange().getValues();
  var orderHeaders = orderData[0];
  var idxOrderLongId = orderHeaders.indexOf("Long Order ID");
  if (idxOrderLongId === -1) return; // Kolom tidak ditemukan

  var existingIds = new Set();
  for (var i = 1; i < orderData.length; i++) {
    var id = orderData[i][idxOrderLongId];
    if (id) existingIds.add(String(id));
  }

  var newRows = [];

  // 2. Ambil data dari Grab
  if (grabSheet) {
    var grabData = grabSheet.getDataRange().getValues();
    var grabHeaders = grabData[0];
    var idxGrabLongId = grabHeaders.indexOf("Long Order ID");
    
    if (idxGrabLongId !== -1) {
      for (var j = 1; j < grabData.length; j++) {
        var grabId = String(grabData[j][idxGrabLongId]);
        if (grabId && grabId !== "" && !existingIds.has(grabId)) {
          newRows.push(grabId);
          existingIds.add(grabId);
        }
      }
    }
  }

  // 3. Ambil data dari Shopee
  if (shopeeSheet) {
    var shopeeData = shopeeSheet.getDataRange().getValues();
    var shopeeHeaders = shopeeData[0];
    var idxShopeeId = shopeeHeaders.indexOf("Transaction ID (Order ID)");
    
    if (idxShopeeId !== -1) {
      for (var k = 1; k < shopeeData.length; k++) {
        var shopeeId = String(shopeeData[k][idxShopeeId]);
        if (shopeeId && shopeeId !== "" && !existingIds.has(shopeeId)) {
          newRows.push(shopeeId);
          existingIds.add(shopeeId);
        }
      }
    }
  }

  // 4. Append baris baru jika ada (Hanya kolom Long Order ID)
  if (newRows.length > 0) {
    // Kita buat array 2D untuk satu kolom saja
    var columnData = newRows.map(function(id) { return [id]; });
    
    // Tentukan range: Baris setelah baris terakhir, Kolom idxOrderLongId + 1
    orderSheet.getRange(orderSheet.getLastRow() + 1, idxOrderLongId + 1, columnData.length, 1).setValues(columnData);
  }
}

function createResponse(status, message) {
  return ContentService.createTextOutput(JSON.stringify({status: status, message: message}))
    .setMimeType(ContentService.MimeType.JSON);
}
