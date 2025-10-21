import {Component} from 'react';
import { Spin } from "antd";

interface LoadingProps {
    message?: string;
}

class Loading extends Component<LoadingProps> {
    render() {
        return (
            <div style={{ paddingTop: 100, marginBottom: 20, textAlign: 'center' }}>
                <Spin size="large" />
                <p>{this.props.message}</p>
            </div>
        );
    }
}

export default Loading;