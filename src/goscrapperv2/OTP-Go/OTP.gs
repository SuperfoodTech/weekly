function doGet(e) {
  // Gunakan objek parameter default jika dijalankan manual dari editor Apps Script (e = undefined)
  var parameter = (e && e.parameter) ? e.parameter : { action: "getOtpEmail", label: "OTP-GO" };
  var action = parameter.action;
  
  if (action === "getOtpEmail" || action === "getOtp") {
    var label = parameter.label || "OTP-GO";
    var otp = ambilOtpDariGmail(label);
    
    // Jika dijalankan dari editor (e tidak ada), log hasilnya agar terlihat di konsol editor
    if (!e) {
      Logger.log("Hasil OTP yang ditemukan di Gmail: " + otp);
    }
    
    return ContentService.createTextOutput(otp)
      .setMimeType(ContentService.MimeType.TEXT);
  }
  
  return ContentService.createTextOutput("Gojek OTP Service Active. Use action=getOtpEmail");
}

function ambilOtpDariGmail(labelName) {
  try {
    var threads = [];
    var label = GmailApp.getUserLabelByName(labelName);
    if (label) {
      threads = label.getThreads(0, 5); // Ambil hingga 5 thread terbaru
    } else {
      threads = GmailApp.search("label:" + labelName + " OR subject:OTP", 0, 5);
    }
    
    var allMessages = [];
    for (var i = 0; i < threads.length; i++) {
      var msgs = threads[i].getMessages();
      for (var j = 0; j < msgs.length; j++) {
        allMessages.push(msgs[j]);
      }
    }
    
    if (allMessages.length > 0) {
      // Urutkan pesan berdasarkan tanggal dari yang paling baru ke terlama
      allMessages.sort(function(a, b) {
        return b.getDate().getTime() - a.getDate().getTime();
      });
      
      var latestMessage = allMessages[0];
      var date = latestMessage.getDate();
      
      // Validasi usia email: jika lebih tua dari 3 menit, anggap usang/kedaluwarsa
      var ageMinutes = (new Date().getTime() - date.getTime()) / (1000 * 60);
      if (ageMinutes > 3.0) {
        return "";
      }
      
      var body = latestMessage.getPlainBody();
      var subject = latestMessage.getSubject();
      
      // Ekstrak OTP dengan regex khusus untuk menghindari tahun 2025/2026/2027/2028
      var otp = "";
      var patterns = [
        /kode verifikasi \(OTP\)[^\d]*(\d{4,6})/i,
        /verification code[^\d]*(\d{4,6})/i,
        /kode OTP[^\d]*(\d{4,6})/i,
        /OTP[^\d]*(\d{4,6})/i,
        /kode[^\d]*(\d{4,6})/i,
        /code[^\d]*(\d{4,6})/i
      ];
      
      for (var p = 0; p < patterns.length; p++) {
        var match = body.match(patterns[p]);
        if (match) {
          var val = match[1];
          if (val !== "2025" && val !== "2026" && val !== "2027" && val !== "2028") {
            otp = val;
            break;
          }
        }
      }
      
      if (!otp) {
        // Fallback: cari angka 4-6 digit apa saja di body yang bukan tahun
        var matches = body.match(/\b\d{4,6}\b/g);
        if (matches) {
          for (var m = 0; m < matches.length; m++) {
            var val = matches[m];
            if (val !== "2025" && val !== "2026" && val !== "2027" && val !== "2028") {
              otp = val;
              break;
            }
          }
        }
      }
      
      if (!otp && subject) {
        // Fallback ke subjek
        var subMatch = subject.match(/\b\d{4,6}\b/);
        if (subMatch) {
          otp = subMatch[0];
        }
      }
      
      if (otp) {
        return otp;
      }
    }
    return "";
  } catch (err) {
    return "Error: " + err.toString();
  }
}
