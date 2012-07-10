/**
 * Created with PyCharm.
 * User: omniboomer
 * Date: 2012-06-06
 * Time: 14.21
 * To change this template use File | Settings | File Templates.
 */

var pc;
var addButton;
var selfView;
var remoteView;

var signalingChannel;

window.onload = function () {
    document.getElementById("call_button").onclick = initiateCall;
    addButton = document.getElementById("add_button");

    selfView = document.getElementById("self_view");
    remoteView = document.getElementById("remote_view");

    signalingChannel = new SignalingChannel();

    // setup message handler to handle an incoming call
    signalingChannel.onmessage = function (evt) {
        configurePeer(evt.data);
    };
};

function initiateCall() {
    configurePeer();
}

// JSEP
function configurePeer(initialOffer) {
    navigator.webkitGetUserMedia({"audio": true, "video": true}, function (localStream) {
        var updateOffer;
        var hasOutstandingOffer = false;
        var hasPendingStreamsToOffer = false;
        var calleeIceStarted = false;

        // create a new PeerConnection object and direct all generated ice candidate messages
        // to the other peer via the signaling channel
        pc = new webkitPeerConnection("STUN stunserver.org", function (candidate) {
            signalingChannel.send(JSON.stringify({ "type": "candidate", "candidate": candidate }));
        });

        function createAndSendUpdateOffer() {
            // create a new updated sdp offer and send it to the other peer via the signaling channel
            // (we can't call setLocalDescription() rigth away so we store the sdp offer in local variable)
            updateOffer = pc.createOffer();
            signalingChannel.send(JSON.stringify({ "type": "offer", "sdp": updateOffer }));

            // mark that we have an outstanding offer
            hasOutstandingOffer = true;
        }

        // reset message handler to handle incoming signaling messages
        signalingChannel.onmessage = function (evt) {
            var msg = JSON.parse(evt.data);

            if (msg.type == "candidate") {
                // feed any incoming candidates to our PeerConnection
                pc.processIceMessage(msg.candidate);

                // time for callee to start ice processing
                if (initialOffer && !calleeIceStarted) {
                    pc.connect();
                    calleeIceStarted = true;
                }

            } else if (msg.type == "offer") {
                // feed the sdp offer into PeerConnection
                pc.setRemoteDescription(PeerConnection.SDP_OFFER, msg.sdp);

                // create an sdp answer based on the offer and set it as our local description
                var answer = pc.createAnswer(msg.sdp);
                pc.setLocalDescription(PeerConnection.SDP_ANSWER, answer);

                // send the answer via the signaling channel
                signalingChannel.send(JSON.stringify({ "type": "answer", "sdp": answer }));

            } else if (msg.type == "answer") {
                // if the answer corresponds to an updated offer (i.e. not the initial offer),
                // we need to process both the updated offer as well as the received answer
                if (!msg.initialAnswer)
                    pc.setLocalDescription(PeerConnection.SDP_OFFER, updateOffer);
                pc.setRemoteDescription(PeerConnection.SDP_ANSWER, msg.sdp);

                // mark that we have received an answer and no longer has an outstanding offer
                hasOutstandingOffer = false;

                // offer any pending streams added while we had an outstanding offer
                if (hasPendingStreamsToOffer) {
                    createAndSendUpdateOffer();
                    hasPendingStreamsToOffer = false;
                }
            }
        };

        // once remote stream arrives, show it in the remote view video element
        pc.onaddstream = function (evt) {
            remoteView.src = webkitURL.createObjectURL(evt.stream);
        };

        // once the PeerConnection is open, prepare for adding a new stream to call
        pc.onopen = function () {
            addButton.onclick = function () {
                navigator.webkitGetUserMedia({"audio": true, "video": true}, function (localStream) {
                    // show the new stream in the self-view
                    selfView.src = webkitURL.createObjectURL(localStream);

                    // add the new local stream  to be sent
                    pc.addStream(localStream);

                    // check if we have an outstanding offer (i.e. we can't send a new one until
                    // we have received an answer)
                    if (hasOutstandingOffer) {
                        hasPendingStreamsToOffer = true;
                        return;
                    }

                    createAndSendUpdateOffer();
                });
            };
        };

        // show local stream as self-view
        selfView.src = webkitURL.createObjectURL(localStream);

        // if we have an initial offer, we're being called; otherwise we're initiating a call
        if (initialOffer) {
            // parse the incoming offer
            var offer = JSON.parse(initialOffer);

            // feed the sdp offer into PeerConnection
            pc.setRemoteDescription(PeerConnection.SDP_OFFER, offer.sdp);

            // add the reply stream to be sent
            pc.addStream(localStream);

            // create an sdp answer based on the offer and set it as our local description
            var answer = pc.createAnswer(offer.sdp);
            pc.setLocalDescription(PeerConnection.SDP_ANSWER, answer);

            // send the answer via the signaling channel (mark it as an anser to the initial offer)
            signalingChannel.send(JSON.stringify({ "type": "answer", "initialAnswer": true, "sdp": answer }));
        } else { // we're initiating a call
            // add the stream to be sent
            pc.addStream(localStream);

            // create the initial sdp offer and set it as our local description
            var offer = pc.createOffer();
            pc.setLocalDescription(PeerConnection.SDP_OFFER, offer);

            // send the offer to the other peer via the signaling channel
            signalingChannel.send(JSON.stringify({ "type": "offer", "sdp": offer }));

            // start gathering candidates
            pc.connect();
        }
    });
}