fs     = require 'fs'
io     = require('socket.io').listen 8888
redis  = require 'redis'
client = redis.createClient()

io.sockets.on 'connection', (socket) ->

    socket.on 'subscribe:feeds', (feeds) ->
        socket.subscribe = redis.createClient()
        
        console.log "Subscribing to #{feeds.length} feeds"
        socket.subscribe.subscribe feeds
        
        socket.subscribe.on 'message', (channel, message) ->
            console.log "Update on #{channel}: #{message}"
            socket.emit 'feed:update', channel
    
    socket.on 'disconnect', () ->
        socket.subscribe?.end()
        console.log 'Disconnect'
    