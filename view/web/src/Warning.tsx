import { List, Flex, Button, Result, message, Modal } from "antd";
import Loading from "./loading";
import { useState } from "react";

interface Alert {
    id: string;
    text: string;
}

function Warning() {
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [ready, setReady] = useState(false);
    const fetchAlerts = async () => {
        if (!window.pywebview) {
            message.error('未检测到监考客户端活动，请稍后重试');
            return;
        }
        try {
            const res = await window.pywebview.api.getAlerts();
            if (!res) {
                setTimeout(fetchAlerts, 1000);
                return;
            }
            setAlerts(res);
            setReady(true);
        } catch (e) {
            setTimeout(fetchAlerts, 1000);
            message.error(`获取警告信息失败，${(e as Error).message}`);
        }
    };

    if (!ready) {
        fetchAlerts();
        return <Loading message="正在检测考试环境" />;
    }

    const info: Set<string> = new Set();
    for (const alert of alerts) {
        const id = alert.id.split('-')[0].toUpperCase();
        if (id === 'VM') {
            info.add('检测到虚拟机环境，请关闭虚拟机');
        } else if (id === 'VRAM') {
            info.add('检测到异常的显存占用，请关闭其他占用显存的程序');
        } else if (id === 'NET') {
            info.add('检测到互联网联通，请断开网络连接');
        } else if (id === 'MEM') {
            info.add('检测到异常的内存使用，请关闭其他占用内存的程序');
        }
    }

    return (
        <div style={{ padding: 20, height: 'calc(100vh - 60px)',width: 'calc(100vw - 60px)' }}>
            <Flex vertical 
            align={info.size !== 0 ? "flex-end" : "center"} 
            justify={info.size !== 0 ? "space-between" : "center"} 
            style={{ height: '100%', width: '100%' }}
        >
                <div style={{width: '100%'}}>   
                    {
                        info.size === 0 ? (
                            <Result
                                status="success"
                                title="考试环境检测通过"
                            />
                        ) : (
                            <List
                                header={<div>警告信息 <a onClick={fetchAlerts} style={{ float: 'right' }}>刷新</a></div>}
                                bordered
                                style={{width: '100%'}}
                                dataSource={Array.from(info)}
                                renderItem={item => (
                                    <List.Item>
                                        {item}
                                    </List.Item>
                                )}
                            />
                        )
                    }
                </div>
                <Button type="primary" onClick={() => {
                    if (info.size > 0) {
                        Modal.confirm({
                            title: '存在警告信息，是否仍然继续？',
                            content: '如果警告信息不属实，请先联系监考员核实',
                            onOk() {
                                window.location.hash = '#/capture';
                                window.location.reload();
                            },
                            okText: '继续',
                            cancelText: '取消',
                        });
                        return;
                    }
                    window.location.hash = '#/capture';
                }}>
                    下一步
                </Button>
            </Flex>
        </div>
    );
}

export default Warning;
