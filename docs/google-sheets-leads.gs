// Google Apps Script: saves chat leads into a Google Sheet.
// Setup: open your Sheet > Extensions > Apps Script, paste this, then
// Deploy > New deployment > type "Web app", Execute as "Me", Who has access "Anyone".
// Copy the web app URL into the LEAD_WEBHOOK_URL setting on your server.
function doPost(e) {
  var lead = JSON.parse(e.postData.contents);
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["Saved at", "Name", "Phone", "Email", "Preferred contact time", "Summary"]);
  }
  sheet.appendRow([lead.saved_at, lead.name, lead.phone, lead.email, lead.preferred_contact_time, lead.summary]);
  return ContentService.createTextOutput("ok");
}
