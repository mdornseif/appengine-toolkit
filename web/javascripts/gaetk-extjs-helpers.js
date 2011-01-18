/*!
 * div. Hilfsfunktionen, die immer wieder fuer die verschiedenen
 * ExtJS-GUIs gebraucht werden koennen
 */

Hudora = {
}

Hudora.Helpers = function() {
  return {
    /**
     * Eine eine Ext.MessageBox an, die aehnlich wie die Standard-Wait-
     * Messagebox funktioniert, nur das statt eines durchlaufenden Balkens
     * ein Spinner-Image auf der linken Seite angezeigt wird. Die MessageBox
     * verschwindet nicht von alleine, sondern muss programatisch via der
     * Methode {@link Ext.MessageBox#hide} wieder entfernt werden.
     * @param {String} message der in der Box angezeigte Text
     */
    spinnerMessageBox: function(message) {
      Ext.MessageBox.show({
        msg: message,
        width: 350,
        closable: false,
        icon: 'hudora-activity-spinner'
      });
    },

    /**
     * Shortcut zum Anzeigen einer Fehlermeldung, damit man nicht jedesmal
     * sechs Zeilen statt einer schreiben muss. Davon abgesehen ist es aber
     * die normale {@link Ext.MessageBox#show}-Box.
     * @param {String} title die Titelbeschriftung fuer die Fehlermeldung
     * @param {String} message die angezeigte Nachricht
     */
    errorMessageBox: function(title, message) {
      Ext.Msg.show({
        title: title,
        msg: message,
        buttons: Ext.Msg.OK,
        icon: Ext.MessageBox.ERROR
      });
    }
  };
}();
