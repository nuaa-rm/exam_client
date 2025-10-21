import React, { useEffect, useRef, useState } from 'react'
import { Row, Col, Select, Card, Button, message, Typography } from 'antd'
import Hls from 'hls.js'
import { CloseOutlined, ReloadOutlined } from '@ant-design/icons'
import Loading from './loading'

const { Title } = Typography

type Devices = {
	monitors: { [key: number]: string }
	cameras: { [key: number]: string }
}

// Local alias to the global pywebview API type (fallback to any if not resolved by TS)
type PyWebviewApi = NonNullable<Window['pywebview']>['api']

function Capture() {
	const [devices, setDevices] = useState<Devices>({ monitors: {}, cameras: {} })
	const [loadingDevices, setLoadingDevices] = useState(true)

	const [selectedMonitor, setSelectedMonitor] = useState<string | null>(null)
	const [selectedCamera, setSelectedCamera] = useState<string | null>(null)

	const [screenLoading, setScreenLoading] = useState(false)
	const [cameraLoading, setCameraLoading] = useState(false)

	// error states when retries exhausted
	const [screenError, setScreenError] = useState(false)
	const [cameraError, setCameraError] = useState(false)

	const screenVideoRef = useRef<HTMLVideoElement | null>(null)
	const cameraVideoRef = useRef<HTMLVideoElement | null>(null)

	// capture health polling state: null = unknown, true = healthy, false = unhealthy
	const [captureHealthy, setCaptureHealthy] = useState<boolean | null>(null)
	const captureHealthTimerRef = useRef<number | null>(null)

	const hlsScreenRef = useRef<Hls | null>(null)
	const hlsCameraRef = useRef<Hls | null>(null)

	// per-stream retry state
	const hlsScreenRetryRef = useRef({ count: 0, timer: null as null | number })
	const hlsCameraRetryRef = useRef({ count: 0, timer: null as null | number })

	function ensureApiReady(): Promise<PyWebviewApi> {
		const ready = () => window.pywebview?.api && Object.keys(window.pywebview.api).length > 0
		if (ready()) return Promise.resolve(window.pywebview!.api)
		return new Promise((resolve) => {
			const poll = () => {
				if (ready()) resolve(window.pywebview!.api)
				else window.setTimeout(poll, 200)
			}
			poll()
		})
	}

	useEffect(() => {
		let mounted = true
		async function load() {
			try {
				let api: PyWebviewApi
				try {
					api = await ensureApiReady()
				} catch {
					message.warning('pywebview API not available — running in dev mode')
					setLoadingDevices(false)
					return
				}
				const res = await api.getAvailableDevices()
				if (!mounted) return
				setDevices(res)
			} catch (err) {
				console.error(err)
				message.error('获取设备列表失败')
			} finally {
				setLoadingDevices(false)
			}
		}
		load()
		return () => {
			mounted = false
		}
	}, [])

	async function refreshDevices() {
		setLoadingDevices(true)
		try {
			const api = await ensureApiReady()
			const res = await api.getAvailableDevices()
			setDevices(res)
			setSelectedMonitor(null)
			setSelectedCamera(null)
			message.success('设备列表已刷新')
		} catch (err) {
			console.error('刷新设备列表失败', err)
			message.error('刷新设备列表失败')
		} finally {
			setLoadingDevices(false)
		}
	}

	function streamUrlFor(name: string, idx: number) {
		const safe = Array.from(name, (ch) => (ch.charCodeAt(0) < 128 ? ch : '_')).join('')
		const suffix = safe === name ? '' : `_${Number.isFinite(idx) ? idx : ''}`
		return `/recorder/live/${encodeURIComponent(`${safe}${suffix}`)}.m3u8`
	}

	function destroyHls(hlsRef: React.MutableRefObject<Hls | null>) {
		hlsRef.current?.destroy()
		hlsRef.current = null
	}

	function clearRetry(ref: React.MutableRefObject<{ count: number; timer: number | null }>) {
		ref.current.count = 0
		if (ref.current.timer) {
			clearTimeout(ref.current.timer)
			ref.current.timer = null
		}
	}

	function attachStream(videoEl: HTMLVideoElement | null, url: string, hlsRef: React.MutableRefObject<Hls | null>) {
		if (!videoEl) return
		destroyHls(hlsRef)
		const retryRef = hlsRef === hlsScreenRef ? hlsScreenRetryRef : hlsCameraRetryRef
		clearRetry(retryRef)

		if (Hls.isSupported()) {
			const hls = new Hls()
			hlsRef.current = hls
			hls.loadSource(url)
			hls.attachMedia(videoEl)

			const MAX_RETRIES = 5
			const BASE_DELAY = 1000

			hls.on(Hls.Events.MANIFEST_PARSED, () => {
				videoEl.play().catch(() => undefined)
			})

			hls.on(Hls.Events.ERROR, (_ev, data) => {
				console.warn('hls error', data)
				if (!data?.fatal) return

				if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
					try {
						hls.recoverMediaError()
						return
					} catch (e) {
						console.warn('recoverMediaError failed', e)
					}
				}

				if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
					try {
						hls.startLoad()
						return
					} catch (e) {
						console.warn('startLoad failed', e)
					}
				}

				const state = retryRef.current
				if (state.count >= MAX_RETRIES) {
					console.error('hls: exceeded max retries, giving up')
					if (retryRef === hlsScreenRetryRef) setScreenError(true)
					else setCameraError(true)
					return
				}

				const delay = BASE_DELAY * Math.pow(2, state.count)
				state.count += 1
				destroyHls(hlsRef)
				if (state.timer) clearTimeout(state.timer)
				state.timer = window.setTimeout(() => {
					state.timer = null
					attachStream(videoEl, url, hlsRef)
				}, delay)
			})
		} else {
			videoEl.src = url
			videoEl.play().catch(() => undefined)
		}
	}

	async function onSelectMonitor(value: string) {
		setSelectedMonitor(value)
		const name = devices.monitors[Number(value)] ?? value
		setScreenLoading(true)
		try {
			const api = await ensureApiReady()
			const ok = await api.startScreenRecorder(Number(value), name)
			if (!ok) {
				message.error('打开屏幕预览失败')
				return
			}
			const url = streamUrlFor(name, Number(value))
			attachStream(screenVideoRef.current, url, hlsScreenRef)
		} catch (err) {
			console.error(err)
			message.error('打开屏幕预览失败')
		} finally {
			setScreenLoading(false)
			try {
				await pollCaptureHealthOnce()
			} catch (e) {
				console.warn('failed to refresh capture health after startScreenRecorder', e)
			}
		}
	}

	async function onSelectCamera(value: string) {
		setSelectedCamera(value)
		const name = devices.cameras[Number(value)] ?? value
		setCameraLoading(true)
		try {
			const api = await ensureApiReady()
			const ok = await api.startCameraRecorder(Number(value), name)
			if (!ok) {
				message.error('打开摄像头预览失败')
				return
			}
			const url = streamUrlFor(name, Number(value))
			attachStream(cameraVideoRef.current, url, hlsCameraRef)
		} catch (err) {
			console.error(err)
			message.error('打开摄像头预览失败')
		} finally {
			setCameraLoading(false)
			try {
				await pollCaptureHealthOnce()
			} catch (e) {
				console.warn('failed to refresh capture health after startCameraRecorder', e)
			}
		}
	}

	const pollCaptureHealthOnce = React.useCallback(async () => {
		try {
			const api = await ensureApiReady()
			const ok = await api.captureHealth()
			setCaptureHealthy(!!ok)
		} catch (err) {
			console.error('poll captureHealth failed', err)
			setCaptureHealthy(false)
		}
	}, [])

	useEffect(() => {
		pollCaptureHealthOnce()
		captureHealthTimerRef.current = window.setInterval(pollCaptureHealthOnce, 3000)
		return () => {
			if (captureHealthTimerRef.current) {
				clearInterval(captureHealthTimerRef.current)
				captureHealthTimerRef.current = null
			}
		}
	}, [pollCaptureHealthOnce])

	async function onNext() {
		try {
			const api = await ensureApiReady()
			const ok = await api.captureHealth()
			setCaptureHealthy(!!ok)
			if (ok) {
				window.location.href = `http://${await api.getEndpoint()}/exam`
			} else {
				message.error('录像未正常开启')
			}
		} catch (err) {
			console.error('captureHealth check failed on Next', err)
			setCaptureHealthy(false)
			message.error('获取录像状态失败')
		}
	}

	useEffect(() => {
		return () => {
			destroyHls(hlsScreenRef)
			destroyHls(hlsCameraRef)
		}
	}, [])

	if (loadingDevices) return <Loading message='正在获取屏幕和摄像头信息' />

	const monitorOptions = Object.entries(devices.monitors).map(([id, name]) => ({ value: id, label: name }))
	const cameraOptions = Object.entries(devices.cameras).map(([id, name]) => ({ value: id, label: name }))

	return (
		<div>
			<div style={{ padding: 24, height: '100vh', boxSizing: 'border-box', position: 'relative' }}>
				<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 20 }}>
					<Title level={3} style={{ margin: 0 }}>请选择屏幕与摄像头</Title>
					<Button icon={<ReloadOutlined />} onClick={refreshDevices} loading={loadingDevices}>
						刷新设备
					</Button>
				</div>
				<Row gutter={16} style={{ height: 'calc(100% - 64px)' }}>
					<Col span={12} style={{ height: '100%' }}>
						<Card title="屏幕预览">
							<Select
								style={{ width: '100%', marginBottom: 12 }}
								options={monitorOptions}
								value={selectedMonitor ?? undefined}
								onChange={onSelectMonitor}
								placeholder="选择需要捕获的屏幕"
							/>
								<div style={{ position: 'relative' }}>
									<video
										ref={(el) => { screenVideoRef.current = el; return undefined }}
										style={{ width: '100%', height: 360, background: '#000' }}
									/>
									{screenLoading && (
										<div style={{
											position: 'absolute',
											top: 0,
											left: 0,
											right: 0,
											bottom: 0,
											display: 'flex',
											alignItems: 'center',
											justifyContent: 'center',
											background: 'rgba(0,0,0,0.25)'
										}}>
											<Loading />
										</div>
									)}

									{screenError && (
										<div style={{
											position: 'absolute',
											top: 0,
											left: 0,
											right: 0,
											bottom: 0,
											display: 'flex',
											alignItems: 'center',
											justifyContent: 'center',
											flexDirection: 'column',
											background: 'rgba(0,0,0,0.5)',
											color: '#fff'
										}}>
											<CloseOutlined style={{ fontSize: 48, color: '#fff' }} />
											<div style={{ marginTop: 8 }}>视频播放失败（已重试多次）</div>
										</div>
									)}
								</div>
						</Card>
					</Col>

					<Col span={12} style={{ height: '100%' }}>
						<Card title="摄像头预览">
							<Select
								style={{ width: '100%', marginBottom: 12 }}
								options={cameraOptions}
								value={selectedCamera ?? undefined}
								onChange={onSelectCamera}
								placeholder="选择要使用的摄像头"
							/>
								<div style={{ position: 'relative' }}>
									<video
										ref={(el) => { cameraVideoRef.current = el; return undefined }}
										style={{ width: '100%', height: 360, background: '#000' }}
									/>
									{cameraLoading && (
										<div style={{
											position: 'absolute',
											top: 0,
											left: 0,
											right: 0,
											bottom: 0,
											display: 'flex',
											alignItems: 'center',
											justifyContent: 'center',
											background: 'rgba(0,0,0,0.25)'
										}}>
											<Loading />
										</div>
									)}

									{cameraError && (
										<div style={{
											position: 'absolute',
											top: 0,
											left: 0,
											right: 0,
											bottom: 0,
											display: 'flex',
											alignItems: 'center',
											justifyContent: 'center',
											flexDirection: 'column',
											background: 'rgba(0,0,0,0.5)',
											color: '#fff'
										}}>
											<CloseOutlined style={{ fontSize: 48, color: '#fff' }} />
											<div style={{ marginTop: 8 }}>视频播放失败（已重试多次）</div>
										</div>
									)}
								</div>
						</Card>
					</Col>
				</Row>

			</div>
			<div style={{ position: 'fixed', right: 24, bottom: 24 }}>
				<Button type="primary" onClick={onNext} disabled={captureHealthy === false}>
					下一步
				</Button>
			</div>
		</div>
	)
}

export default Capture
