/*
* SignalingChannel handles communication with server, in this case the app engine sockets
*/

var onIncomingMessage = function(evt){console.log("Caling uninitialized onIncomingMessages");};

var debugLog = false;

var debug = function(str){
    if(debugLog){
        console.log(str);
    }
}

function SignalingChannel(roomKey, userId, token){

    this.roomKey = roomKey;
    this.userId = userId;
    this.token = token;

    this.onChannelOpened = function() {
        debug('Channel opened.');
    }


    this.onChannelMessage = function(message) {
        debug('S->C: ' + message.data);
        if (message.data != 'BYE') {
            if (message.data.indexOf("\"ERROR\"", 0) == -1) {
                onIncomingMessage(message);
            }
        } else {
            debug('Session terminated.');
        }
    }

    this.onChannelError = function() {
        debug('Channel error.');
    }

    this.onChannelClosed = function() {
        debug('Channel closed.');
    }

    this.close = function(){
        debug("Closing socket");
        this.socket.close();
    };

    //Handle incoming message
    this.onIncomingMessage = function(func){
        onIncomingMessage = func;
    };

    //Handle outgoing message
    this.send = function(message){
        debug('C->S: ' + message);
        path = '/message?r=' + this.roomKey + '&u=' + this.userId;
        var xhr = new XMLHttpRequest();
        xhr.open('POST', path, true);
        xhr.send(message);
    };

    //Initialize connection
    this.initialize = function(){
        debug("Opening channel.");
        this.channel = new goog.appengine.Channel(this.token);
        var handler = {
            onopen: this.onChannelOpened,
            onmessage: this.onChannelMessage,
            onerror: this.onChannelError,
            onclose: this.onChannelClosed
        };

        this.socket = this.channel.open(handler);
    };

}