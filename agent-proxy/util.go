package main

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

func GetCurlCommand(req *http.Request) (string, error) {
	var command []string
	command = append(command, fmt.Sprintf("curl -X %s", req.Method))

	// 1. Append Headers
	for name, values := range req.Header {
		for _, value := range values {
			command = append(command, fmt.Sprintf("-H '%s: %s'", name, value))
		}
	}

	// 2. Append Body
	if req.Body != nil {
		bodyBytes, err := io.ReadAll(req.Body)
		if err != nil {
			return "", err
		}
		// Restore the body so it can be read again by the actual HTTP client
		req.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

		if len(bodyBytes) > 0 {
			command = append(command, fmt.Sprintf("-d '%s'", string(bodyBytes)))
		}
	}

	// 3. Append URL
	command = append(command, fmt.Sprintf("'%s'", req.URL.String()))

	return strings.Join(command, " "), nil
}

func uuidV7() string {
	uuid, err := newUUIDv7()
	if err != nil {
		panic(err)
	}
	return formatUUID(uuid)
}

func newUUIDv7() ([16]byte, error) {
	var uuid [16]byte

	// 48-bit Unix timestamp in milliseconds
	ms := uint64(time.Now().UnixMilli())
	uuid[0] = byte(ms >> 40)
	uuid[1] = byte(ms >> 32)
	uuid[2] = byte(ms >> 24)
	uuid[3] = byte(ms >> 16)
	uuid[4] = byte(ms >> 8)
	uuid[5] = byte(ms)

	// Random bytes for the rest
	if _, err := rand.Read(uuid[6:]); err != nil {
		return uuid, err
	}

	// Set version (4 bits) = 0b0111
	uuid[6] = (uuid[6] & 0x0f) | 0x70

	// Set variant (2 bits) = 0b10
	uuid[8] = (uuid[8] & 0x3f) | 0x80

	return uuid, nil
}

func formatUUID(uuid [16]byte) string {
	var buf [36]byte
	hex.Encode(buf[0:8], uuid[0:4])
	buf[8] = '-'
	hex.Encode(buf[9:13], uuid[4:6])
	buf[13] = '-'
	hex.Encode(buf[14:18], uuid[6:8])
	buf[18] = '-'
	hex.Encode(buf[19:23], uuid[8:10])
	buf[23] = '-'
	hex.Encode(buf[24:36], uuid[10:16])
	return string(buf[:])
}

func now() time.Time {
	loc, err := time.LoadLocation("Asia/Bangkok")
	if err != nil {
		panic(err)
	}
	return time.Now().In(loc)
}

var _ = now()
