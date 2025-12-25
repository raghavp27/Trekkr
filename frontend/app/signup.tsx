import React, { useState } from 'react';
import {
    View,
    Text,
    TextInput,
    TouchableOpacity,
    StyleSheet,
    Alert,
    ActivityIndicator,
    KeyboardAvoidingView,
    Platform,
    ScrollView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '@/contexts/AuthContext';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors } from '@/constants/theme';

export default function SignupScreen() {
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const { register } = useAuth();
    const router = useRouter();
    const colorScheme = useColorScheme();
    const colors = Colors[colorScheme ?? 'light'];

    const validateForm = (): string | null => {
        if (!email.trim() || !username.trim() || !password.trim() || !confirmPassword.trim()) {
            return 'Please fill in all fields';
        }

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
            return 'Please enter a valid email address';
        }

        if (username.trim().length < 3) {
            return 'Username must be at least 3 characters long';
        }

        if (!/^[a-zA-Z0-9_]+$/.test(username.trim())) {
            return 'Username can only contain letters, numbers, and underscores';
        }

        if (password.length < 8) {
            return 'Password must be at least 8 characters long';
        }

        if (!/[a-z]/.test(password)) {
            return 'Password must contain at least one lowercase letter';
        }

        if (!/[A-Z]/.test(password)) {
            return 'Password must contain at least one uppercase letter';
        }

        if (!/[0-9]/.test(password)) {
            return 'Password must contain at least one number';
        }

        if (password !== confirmPassword) {
            return 'Passwords do not match';
        }

        return null;
    };

    const handleSignup = async () => {
        const validationError = validateForm();
        if (validationError) {
            Alert.alert('Validation Error', validationError);
            return;
        }

        setIsLoading(true);
        try {
            await register(email.trim(), username.trim(), password);
            router.replace('/(tabs)');
        } catch (error: any) {
            Alert.alert('Signup Failed', error.message || 'An error occurred during signup');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <KeyboardAvoidingView
            style={[styles.container, { backgroundColor: colors.background }]}
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
            <ScrollView
                contentContainerStyle={styles.scrollContent}
                keyboardShouldPersistTaps="handled"
            >
                <View style={styles.content}>
                    <Text style={[styles.title, { color: colors.text }]}>Create Account</Text>
                    <Text style={[styles.subtitle, { color: colors.icon }]}>
                        Sign up to get started
                    </Text>

                    <View style={styles.form}>
                        <View style={styles.inputContainer}>
                            <Text style={[styles.label, { color: colors.text }]}>Email</Text>
                            <TextInput
                                style={[
                                    styles.input,
                                    {
                                        backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#f5f5f5',
                                        color: colors.text,
                                        borderColor: colors.icon,
                                    },
                                ]}
                                placeholder="Enter your email"
                                placeholderTextColor={colors.icon}
                                value={email}
                                onChangeText={setEmail}
                                autoCapitalize="none"
                                autoCorrect={false}
                                keyboardType="email-address"
                                editable={!isLoading}
                            />
                        </View>

                        <View style={styles.inputContainer}>
                            <Text style={[styles.label, { color: colors.text }]}>Username</Text>
                            <TextInput
                                style={[
                                    styles.input,
                                    {
                                        backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#f5f5f5',
                                        color: colors.text,
                                        borderColor: colors.icon,
                                    },
                                ]}
                                placeholder="Choose a username"
                                placeholderTextColor={colors.icon}
                                value={username}
                                onChangeText={setUsername}
                                autoCapitalize="none"
                                autoCorrect={false}
                                editable={!isLoading}
                            />
                            <Text style={[styles.hint, { color: colors.icon }]}>
                                3-50 characters, letters, numbers, and underscores only
                            </Text>
                        </View>

                        <View style={styles.inputContainer}>
                            <Text style={[styles.label, { color: colors.text }]}>Password</Text>
                            <TextInput
                                style={[
                                    styles.input,
                                    {
                                        backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#f5f5f5',
                                        color: colors.text,
                                        borderColor: colors.icon,
                                    },
                                ]}
                                placeholder="Create a password"
                                placeholderTextColor={colors.icon}
                                value={password}
                                onChangeText={setPassword}
                                secureTextEntry
                                autoCapitalize="none"
                                editable={!isLoading}
                            />
                            <Text style={[styles.hint, { color: colors.icon }]}>
                                At least 8 characters with uppercase, lowercase, and number
                            </Text>
                        </View>

                        <View style={styles.inputContainer}>
                            <Text style={[styles.label, { color: colors.text }]}>Confirm Password</Text>
                            <TextInput
                                style={[
                                    styles.input,
                                    {
                                        backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#f5f5f5',
                                        color: colors.text,
                                        borderColor: colors.icon,
                                    },
                                ]}
                                placeholder="Confirm your password"
                                placeholderTextColor={colors.icon}
                                value={confirmPassword}
                                onChangeText={setConfirmPassword}
                                secureTextEntry
                                autoCapitalize="none"
                                editable={!isLoading}
                            />
                        </View>

                        <TouchableOpacity
                            style={[styles.button, isLoading && styles.buttonDisabled]}
                            onPress={handleSignup}
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <ActivityIndicator color="#fff" />
                            ) : (
                                <Text style={styles.buttonText}>Sign Up</Text>
                            )}
                        </TouchableOpacity>

                        <View style={styles.footer}>
                            <Text style={[styles.footerText, { color: colors.text }]}>
                                Already have an account?{' '}
                            </Text>
                            <TouchableOpacity
                                onPress={() => router.push('/login')}
                                disabled={isLoading}
                            >
                                <Text style={[styles.link, { color: colors.tint }]}>Sign In</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </ScrollView>
        </KeyboardAvoidingView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    scrollContent: {
        flexGrow: 1,
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        padding: 24,
    },
    title: {
        fontSize: 32,
        fontWeight: 'bold',
        marginBottom: 8,
        textAlign: 'center',
    },
    subtitle: {
        fontSize: 16,
        marginBottom: 32,
        textAlign: 'center',
    },
    form: {
        width: '100%',
    },
    inputContainer: {
        marginBottom: 20,
    },
    label: {
        fontSize: 14,
        fontWeight: '600',
        marginBottom: 8,
    },
    input: {
        height: 50,
        borderWidth: 1,
        borderRadius: 8,
        paddingHorizontal: 16,
        fontSize: 16,
    },
    hint: {
        fontSize: 12,
        marginTop: 4,
    },
    button: {
        backgroundColor: '#10b981',
        height: 50,
        borderRadius: 8,
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 8,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    buttonText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    footer: {
        flexDirection: 'row',
        justifyContent: 'center',
        marginTop: 24,
    },
    footerText: {
        fontSize: 14,
    },
    link: {
        fontSize: 14,
        fontWeight: '600',
    },
});

