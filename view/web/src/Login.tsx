import { LockOutlined, UserOutlined, LinkOutlined } from '@ant-design/icons';
import { Button, Form, Input, Flex, message } from 'antd';

interface LoginInfo {
  uname: string;
  password: string;
  endpoint: string;
}

function Login() {
  const onFinish = async (values: LoginInfo) => {
    if (!window.pywebview) {
      message.error('未检测到监考客户端活动，请稍后重试');
      return;
    }
    console.log('Received values of form: ', values);
    try {
      const res = await window.pywebview.api.login(values.uname, values.password, values.endpoint);
      if (!res.success) {
        console.log('Login failed:', res);
        message.error(`登录失败，${res.error || '未知错误'}`);
      } else {
        window.location.hash = '#/warning';
      }
    } catch (e) {
      message.error(`登录失败，${(e as Error).message}`);
    }
  };

  return (
    <Flex align="center" justify="center" vertical style={{ height: '100vh', overflow: 'hidden' }}>
      <Flex justify="center" align="middle">
        <img src="/logo.svg" alt="Logo" style={{ width: '50px' }} />
        <h2 className="logo-title">长空御风</h2>
      </Flex>
      <p style={{ textAlign: 'center', margin: 0}}>监考系统客户端</p>
      <Form
        name="login"
        initialValues={{ remember: true }}
        style={{ width: 360, padding: '20px', marginBottom: '100px' }}
        onFinish={onFinish}
      >
        <Form.Item
          name="endpoint"
          rules={[{ required: true, message: '请输入接口地址' }]}
        >
          <Input prefix={<LinkOutlined />} placeholder="接口地址" />
        </Form.Item>
        <Form.Item
          name="uname"
          rules={[{ required: true, message: '请输入用户名' }]}
        >
          <Input prefix={<UserOutlined />} placeholder="用户名" />
        </Form.Item>
        <Form.Item
          name="password"
          rules={[{ required: true, message: '请输入密码' }]}
        >
          <Input prefix={<LockOutlined />} type="password" placeholder="密码" />
        </Form.Item>

        <Form.Item>
          <Button block type="primary" htmlType="submit">
            登录
          </Button>
        </Form.Item>
      </Form>
    </Flex>
  );
}

export default Login
